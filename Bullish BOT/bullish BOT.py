import requests
import json
from datetime import datetime, timedelta
import pickle
import time
from operator import itemgetter

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

bittrex_session = requests.Session()

look_back_period = [10, 50]
price_increase_requirement = 0.10	#format 0.25 = 25%; 0.44 = 44%
extra_look_back_period = 10
price_entry_level = 0.2	#format 0.2 = 20%; 0.25 = 25%
#"oneMin", "fiveMin", "thirtyMin", "hour" and "day"
interval = 'day'
list_of_email_addresses = ['joewaltman@gmail.com', 'shaltcoin-screener@googlegroups.com', 'ovidiu162000@yahoo.com'] #

if interval =='day':
	period = 'day'
	one_period = timedelta(days=1)
elif interval == 'hour':
	period = 'hour'
	one_period = timedelta(hours=1)
elif interval == 'thirtyMin':
	period = 'thirtyMin'
	one_period = timedelta(minutes=30)

def SendEmail(subject, body):
	gmail_user = "shaltcoinscreener@gmail.com"  
	gmail_password = "shalt123"
	
	sent_from = gmail_user
	
	for to in list_of_email_addresses:
		msg = MIMEMultipart('alternative')
		msg['Subject'] = subject
		msg['From'] = sent_from
		msg['To'] = to
		email_text = MIMEText(body, 'plain')
		msg.attach(email_text)
		
		try:  
			server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
			server.ehlo()
			server.login(gmail_user, gmail_password)
			server.sendmail(sent_from, to, msg.as_string())
			server.close()
			print("Email sent!")
		except:
			print("Something went wrong with email")

def ComposeEmail(btc_coins, coins_with_increase_window, coins_with_low_after_window, coins_with_non_adj_lows, coins_with_entries):
	
	list_coins_with_non_adj_lows = []
	for D in coins_with_non_adj_lows:
		list_coins_with_non_adj_lows.append(D['coin'])
	
	email_info = open("email_info.txt","w")
	
	email_info.write('Total number of Bittrex coins: ' + str(len(btc_coins)) + '\n')
	email_info.write('Price increase requirement: ' + str(int(price_increase_requirement*100)) + '%' + '\n')
	email_info.write('Coins with price increase window: ' + str(len(coins_with_increase_window)) + '\n')
	email_info.write('Coins with low(between 33% and 66%) after window: ' + str(len(coins_with_low_after_window)) + '\n')
	email_info.write('Coins with non adjacent lowest points: ' + str(len(coins_with_non_adj_lows)) + ' - ' + str(list_coins_with_non_adj_lows) +  '\n')
	email_info.write('Coins with entries at the 25% level: ' + str(len(coins_with_entries)) +  '\n')
	email_info.write('-------------------------------------------------------------------------------------')
	email_info.write('\n')
	email_info.write('\n')
	
	if len(coins_with_entries) > 0:
		for C in coins_with_entries:
			email_info.write(C['coin'] + ' - https://bittrex.com/Market/Index?MarketName=BTC-' + C['coin'] + '\n')
			email_info.write('Window increase - ' + str(int(C['increase']*100)) + '%' + '\n')
			email_info.write('Low on ' + C['min price date'].strftime('%Y-%m-%d') + ' at ' + ('%.8f' %C['min price']) + '\n')
			email_info.write('High on ' + C['max price date'].strftime('%Y-%m-%d') + ' at ' + ('%.8f' %C['max price']) + '\n')
			email_info.write('Low after window on '  + C['lowest low date'].strftime('%Y-%m-%d') + ' at ' + ('%.8f' %C['lowest low']) + '\n')
			email_info.write('First non adjacent low ' +  C['first low date'].strftime('%Y-%m-%d') + ' at ' + ('%.8f' %C['first low']) + '\n')
			email_info.write('Second non adjacent low ' +  C['second low date'].strftime('%Y-%m-%d') + ' at ' + ('%.8f' %C['second low']) + '\n')
			email_info.write(str(len(C['entries'])) + ' entry points at the ' + str(int(price_entry_level*100)) + '% level - price ' + ('%.8f' %C['entry level']) + '\n')
			email_info.write('\n')
	email_info.close()
	
	email_info = open("email_info.txt","r")
	now = datetime.today() - timedelta(hours=10)	#timedelta(hours=7)
	now = now.strftime("%d-%m-%Y")
	subject = "Shaltcoin Screener - Bullish BOT coins for " + str(now)
	body = email_info.read()
	SendEmail(subject, body)
			
def get_btc_coins():
	btcmarkets = []
	url = 'https://bittrex.com/api/v1.1/public/getmarkets'
		
	count = 0
	while True:
		try:
			response = bittrex_session.get(url)
		except requests.exceptions.RequestException as e:
			count = count + 1
			print("Bittrex - Error while request prices ", str(e))
			if count == 10:
				print("Bittrex - Tried to request prices 10 times and failed. Exiting script!")
				error_message = str(e)
				now = datetime.today() - timedelta(hours=7)
				now = now.strftime("%d-%m-%Y  %H:%M")
				subject = "Script error " + str(now)
				SendEmail(subject, error_message)
				sys.exit()
			continue
		else:
			break
	
	try:
		data = json.loads(response.text)
	except Exception as e:
		error_message = str(e)
		now = datetime.today() - timedelta(hours=7)
		now = now.strftime("%d-%m-%Y  %H:%M")
		subject = "Script error " + str(now)
		SendEmail(subject, error_message)
		sys.exit()
		
	if data['success']:
		for D in data['result']:
			if D['BaseCurrency'] == 'BTC' and D['IsActive']:
				btcmarkets.append(D['MarketCurrency'])
	else:
		error_message = data['message']
		now = datetime.today() - timedelta(hours=7)
		now = now.strftime("%d-%m-%Y  %H:%M")
		subject = "Script error " + str(now)
		SendEmail(subject, error_message)
		sys.exit()
	btcmarkets.sort()
	return btcmarkets

def get_historical_prices(coin, interval):
	url = "https://bittrex.com/Api/v2.0/pub/market/GetTicks?marketName=BTC-"+coin+"&tickInterval="+interval
	while True:
		response = bittrex_session.get(url)
		data = json.loads(response.text)
		if (data != None) and (data['success'] == True) and (data['result'] != None):
			break
		else:
			time.sleep(1)
	return data

def find_min_and_max_from_period(coin, OHLC, period):
	data = []
	i = 0
	while True:
		start_period = len(OHLC) - 2*period - i*extra_look_back_period
		end_period = len(OHLC)
		min_price = 99999999999
		max_price = 0
		OHLC_to_test = OHLC[start_period:end_period]

		for D in OHLC_to_test:
			if D[3] < min_price:
				min_price = D[3]
				min_price_date = D[0]
			if D[2] > max_price:
				max_price = D[2]
				max_price_date = D[0]
		if (min_price_date < max_price_date) and ((max_price/min_price - 1) > price_increase_requirement):
			i = i + 1
			data.append([min_price, min_price_date, max_price, max_price_date, max_price/min_price - 1])
			if (len(data) > 1) and (data[-1][1] == data[-2][1]):
				break
		else:
			break

	return data
	
def find_increase(coin, OHLC):
	dict_data = {}
	for L in range(look_back_period[0], look_back_period[1]):
		data = find_min_and_max_from_period(coin, OHLC, L)
		if len(data) != 0:
			dict_data = {'coin' : coin, 'min price' : data[-1][0], 'min price date' : data[-1][1], 
						'max price' : data[-1][2], 'max price date' : data[-1][3], 'increase' : data[-1][4]}
			break
	return dict_data
			
def find_decrease(C, OHLC):
	lows_between_33_and_66 = []
	high_date = C['max price date']
	current_date = OHLC[-1][0]
	lowest_low = 99999999

	if high_date < current_date:
		for D in OHLC:
			if D[0] > high_date and D[3] < lowest_low:
				lowest_low = D[3]
				lowest_low_date = D[0]
		condition_33 = lowest_low > (C['min price'] + ((C['max price'] - C['min price']) * 0.33))
		condition_66 = lowest_low < (C['min price'] + ((C['max price'] - C['min price']) * 0.66))
		if condition_33 and condition_66:
			C['lowest low'] = lowest_low
			C['lowest low date'] = lowest_low_date
			return(C)
		else:
			return {}
	else:
		return {}

def get_non_adj_lows(C, OHLC):
	lows_list = []
	
	for i in range(0, len(OHLC)):
		if OHLC[i][0] == C['lowest low date']:
			start_date = i
			
	if len(OHLC) - start_date > 3:
		for j in range(start_date+1, len(OHLC)):
			lows_list.append([OHLC[j][3], OHLC[j][0]])
		sorted_lows_list = sorted(lows_list, key=itemgetter(0))
		first_low = sorted_lows_list[0]
		second_low = sorted_lows_list[1]
		if (first_low[1] < (second_low[1] - 2*one_period)):	#(C['lowest low date'] < (first_low[1] - one_period)) and 
			C['first low'] = first_low[0]
			C['first low date'] = first_low[1]
			C['second low'] = second_low[0]
			C['second low date'] = second_low[1]
			return C
		else:
			return {}
	else:
		return {}	

def get_entry_points(C, OHLC):
	entries = []
	for i in range(0, len(OHLC)):
		if OHLC[i][0] == C['second low date']:
			start_date = i
	
	twentyfive_perc_level = ((C['max price'] - C['min price']) * price_entry_level) + C['lowest low']
	C['entry level'] = twentyfive_perc_level
	for j in range(start_date, len(OHLC)):
		if (OHLC[j][3] < twentyfive_perc_level) and (OHLC[j][2] > twentyfive_perc_level):
			entries.append(OHLC[j])
	C['entries'] = entries
	return C		
		
def calculate_indicators(coin):
	
	data = get_historical_prices(coin, interval)
	
	if len(data['result']) > 100:
		OHLC = []

		for info in data['result']:
			day = info['T']		
			day = datetime.strptime(day[:10], '%Y-%m-%d')	#type datetime
			open1 = info['O']	#type float
			high = info['H']
			low = info['L']
			close = info['C']
			volume	= info['V']
			OHLC.append([day, open1, high, low, close, volume])
		
		#removing first data candle, because of incorrect information when first listing on exchange
		del OHLC[0]
	#print("Starting for", coin, " | length data:", len(OHLC))
	
	
		dict_data = find_increase(coin, OHLC)
		if bool(dict_data):
			coins_with_increase_window.append(dict_data)
			decrease = find_decrease(dict_data, OHLC)
			if bool(decrease):
				coins_with_low_after_window.append(decrease)
				non_adj_lows = get_non_adj_lows(decrease, OHLC)
				if bool(non_adj_lows):
					coins_with_non_adj_lows.append(non_adj_lows)
					coins_with_entry_points = get_entry_points(non_adj_lows, OHLC)
					if len(coins_with_entry_points['entries']) > 0:
						coins_with_entries.append(coins_with_entry_points)
					#entry_points(coins_with_non_adj_lows, OHLC)
					#print(non_adj_lows)
	

def main():
	global coins_with_increase_window, coins_with_low_after_window, coins_with_non_adj_lows, coins_with_entries
	btc_coins = get_btc_coins()
	
	#btc_coins = ['ETH', 'LTC', 'NEO']	#LRC
	#btc_coins = ['BTG', 'NXS']
	
	coins_with_increase_window = []
	coins_with_low_after_window = []
	coins_with_non_adj_lows = []
	coins_with_entries = []
	
	# for coin in btc_coins:
		# try:
			# calculate_indicators(coin)
		# except Exception as e:
			# print(coin, str(e))
			
	for coin in btc_coins:
		calculate_indicators(coin)
	
	print("coins_with_increase_window:", len(coins_with_increase_window))
	print("coins_with_low_after_window:", len(coins_with_low_after_window))
	print("coins_with_non_adj_lows:", len(coins_with_non_adj_lows))
	print("coins_with_entries:", len(coins_with_entries))
	print(coins_with_entries)
	ComposeEmail(btc_coins, coins_with_increase_window, coins_with_low_after_window, coins_with_non_adj_lows, coins_with_entries)
	
if __name__ == "__main__":
	main()