import requests
import json
from datetime import datetime, timedelta
import pickle

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

bittrex_session = requests.Session()
williams_period = 21
willy_period = 13
willy_lookback_period = 15	#the number of candles to search for willy condition
macd_ema1 = 9
macd_ema2 = 30
macd_signal = 9
fib_period = [100, 500, 1000]
divergence_period_lengths = [10, 25]		#first value = minimum length, second value = maximum length #NO MORE THAN 2 VALUES! # NO: [5, 10, 25]
divergence_look_back_period = 50
stops = False	# if True it will ask to press a key to continue displaying one result; if False it will continue to display all results.
max_divergences = 5
list_of_email_addresses = ['joewaltman@gmail.com', 'shaltcoin-screener@googlegroups.com', 'ovidiu162000@yahoo.com']	#

total_nr_of_coins = 0

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

def get_btc_coins():
	url = "https://bittrex.com/api/v1.1/public/getmarketsummaries"
	response = bittrex_session.get(url)
	data = json.loads(response.text)
	
	allmarkets = [dct["MarketName"] for dct in data["result"]]

	btcmarkets = []

	for M in allmarkets:
		if M[0] == 'B':
			btcmarkets.append(M[4:])
	return btcmarkets

def get_historical_prices(coin):
	success = False
	url = "https://bittrex.com/Api/v2.0/pub/market/GetTicks?marketName=BTC-"+coin+"&tickInterval=day"
	while not success:
		response = bittrex_session.get(url)
		data = json.loads(response.text)
		success = data['success']
		if data['success'] == False:
			print(coin, "========================", data)
	return data
	
def max_and_min(list):
	maximum = max(list)
	minimum = min(list)
	return maximum, minimum	
	
def log_information(symbol, OHLC):
	file_name = symbol+"_indicators.csv"
	
	if os.path.isfile(file_name):
		print(file_name, "exists")
	else:
		print(file_name, "has to be created")
		column1 = 'Date'
		column2 = 'Open'
		column3 = 'High'
		column4 = 'Low'
		column5 = 'Close'
		column6 = 'Volume'
		
		column7 = 'williams_r(' + str(williams_period) + ')'
		column8 = 'willy(' + str(willy_period) + ')'
		column9 = 'EMA(' + str(macd_ema1) + ')'
		column10 = 'EMA(' + str(macd_ema2) + ')'
		column11 = 'MACD Line'
		column12 = 'MACD Signal(' + str(macd_signal) + ')'
		column13 = 'MACD Histogram'
		
		information = [column1, column2, column3, column4, column5, column6, column7, column8, column9, column10, 
						column11, column12, column13]
		
		h = open(file_name,'w')
		for info in information:
			h.write(info)
			h.write(',')
		h.write("\n")
		h.close()
	
	path = symbol+"_indicators.csv"
	h = open(path, 'a')
	for item in OHLC:
		information = [item[0], '%.8f' %item[1], '%.8f' %item[2], '%.8f' %item[3], '%.8f' %item[4], '%.2f' %item[5], 
					'%.4f' %item[6], '%.4f' %item[7], '%.8f' %item[8], '%.8f' %item[9], '%.8f' %item[10], '%.8f' %item[11], '%.8f' %item[12]]
		for info in information:
			h.write(info)
			h.write(',')
		h.write("\n")
	h.close()
	
def williams_R(OHLC, williams_period):

	for i in range(0, len(OHLC)):
		if i > williams_period:
			lowest_low = 9999999
			highest_high = 00000000
			for j in range((i-williams_period+1), i+1):
				if OHLC[j][3] < lowest_low:
					lowest_low = OHLC[j][3]
				if OHLC[j][2] > highest_high:
					highest_high = OHLC[j][2]
			w_r = (highest_high - OHLC[i][4]) / (highest_high - lowest_low) * (-100)
			OHLC[i].append(w_r)
		else:
			OHLC[i].append(0)

def willy(OHLC, willy_period):
	willy_multiplier = 2 / (willy_period + 1)
	
	for i in range(0, len(OHLC)):
		if OHLC[i][6] == 0:
			k = 0
			OHLC[i].append(0)
		else:
			k = k + 1
		if k == 1:
			OHLC[i].append(OHLC[i][6])
		elif k > 1:
			willy_value = ((OHLC[i][6] - OHLC[i-1][7]) * willy_multiplier) + OHLC[i-1][7]
			OHLC[i].append(willy_value)
			
def check_willy(OHLC, momentum):
	
	willy_data = []
	for i in range((len(OHLC) - willy_lookback_period), len(OHLC)):
		willy_data.append([OHLC[i][0], OHLC[i][7]])
		
	bull_willy = []
	bear_willy = []
	for W in willy_data:
		if W[1] < -75:
			bull_willy.append([W[0], W[1]])
		if W[1] > -25:
			bear_willy.append([W[0], W[1]])
	
	# bull_willy = list of dates and willy value
	# bull_willy = [[date1, value1], [date2, value2], etc]
	if momentum == 'BULL':
		return bull_willy
	else:
		return bear_willy
			
def macd(OHLC, macd_ema1, macd_ema2, macd_signal):
	ema1_multiplier = 2 / (macd_ema1 + 1)
	ema2_multiplier = 2 / (macd_ema2 + 1)
	signal_multiplier = 2 / (macd_signal + 1)
	
	for i in range(0, len(OHLC)):
		if i == 0:
			ema1_for_macd = OHLC[i][4]
			ema2_for_macd = OHLC[i][4]
			macd_line = 0
			macd_signal_line = 0
			macd_histogram = 0
		elif i == 1:
			ema1_for_macd = (OHLC[i][4] - OHLC[i-1][8]) * ema1_multiplier + OHLC[i-1][8]
			ema2_for_macd = (OHLC[i][4] - OHLC[i-1][9]) * ema2_multiplier + OHLC[i-1][9]
			macd_line = ema1_for_macd - ema2_for_macd
			macd_signal_line = macd_line
			macd_histogram = macd_line - macd_signal_line
		elif i > 1:
			ema1_for_macd = (OHLC[i][4] - OHLC[i-1][8]) * ema1_multiplier + OHLC[i-1][8]
			ema2_for_macd = (OHLC[i][4] - OHLC[i-1][9]) * ema2_multiplier + OHLC[i-1][9]
			macd_line = ema1_for_macd - ema2_for_macd
			macd_signal_line = (macd_line - OHLC[i-1][10]) * signal_multiplier + OHLC[i-1][10]
			macd_histogram = macd_line - macd_signal_line
		OHLC[i].append(ema1_for_macd)
		OHLC[i].append(ema2_for_macd)
		OHLC[i].append(macd_line)
		OHLC[i].append(macd_signal_line)
		OHLC[i].append(macd_histogram)

def fib(OHLC, period):

	if period < len(OHLC):
		last_period = len(OHLC) - period
		low_price = OHLC[last_period][3]
		low_date = OHLC[last_period][0]
		high_price = OHLC[last_period][2]
		high_date = OHLC[last_period][0]
		
		for i in range(last_period, len(OHLC)):
			if OHLC[i][3] < low_price:
				low_price = OHLC[i][3]
				low_date = OHLC[i][0]
			if OHLC[i][2] > high_price:
				high_price = OHLC[i][2]
				high_date = OHLC[i][0]
		
		low_date_datetime = datetime.strptime(low_date[:10], '%Y-%m-%d')
		high_date_datetime = datetime.strptime(high_date[:10], '%Y-%m-%d')
		
		fib_level = (OHLC[-1][4] - low_price) / (high_price - low_price)
		
		if (low_date_datetime < high_date_datetime) and (fib_level < 0.382):
			# print("fib_level=", fib_level)
			# print(coin, period, "BULL RLZ!")
			# print(OHLC[-1])
			# print("\n")
			str_low_price = format('%.8f' %low_price)
			str_high_price = format('%.8f' %high_price)
			return ['BULL', period, low_date, str_low_price, high_date, str_high_price, fib_level]
		elif (low_date_datetime > high_date_datetime) and (fib_level > 0.618):
			# print("fib_level=", fib_level)
			# print(coin, period, "BEAR RLZ!")
			# print(OHLC[-1])
			# print("\n")
			str_low_price = format('%.8f' %low_price)
			str_high_price = format('%.8f' %high_price)
			return ['BEAR', period, low_date, str_low_price, high_date, str_high_price, fib_level]
		else:
			return None
	else:
		return None

def get_all_slopes(OHLC, momentum):
	
	def get_slope(candles):
		x, y = [], []
		k = 10
		
		for item in candles:
			y.append(item)
			x.append(k)
			k = k+1
		
		max_x, min_x = max_and_min(x)
		max_y, min_y = max_and_min(y)
		
		new_x, new_y = [], []
		
		for i in range(0, len(x)):
			z = (x[i]-min_x)/(max_x-min_x)
			new_x.append(z)
			z = (y[i]-min_y)/(max_y-min_y)
			new_y.append(z)
			
		x = new_x
		y = new_y

		xy, x2, y2 = [], [], []
		sum_x, sum_y, sum_xy, sum_x2, sum_y2 = 0, 0, 0, 0, 0

		for i in range(0, len(x)):
			xy.append(x[i]*y[i])
			x2.append(x[i]*x[i])
			y2.append(y[i]*y[i])
			sum_x = sum_x + x[i]
			sum_y = sum_y + y[i]
			sum_xy = sum_xy + xy[i]
			sum_x2 = sum_x2 + x2[i]
			sum_y2 = sum_y2 + y2[i]	

		a = ((sum_y*sum_x2)-(sum_x*sum_xy))/((len(x)*sum_x2)-sum_x*sum_x)
		b = ((len(x)*sum_xy)-(sum_x*sum_y))/((len(x)*sum_x2)-sum_x*sum_x)
		slope = b
		#print("Am calculat slope")
		return slope
	
	bull_divergences = []
	bear_divergences = []
	
	if momentum == 'BULL':
		data = []
		nr_of_bull_divergences = 0
		for i in range((len(OHLC) - divergence_look_back_period), len(OHLC)):
			data.append([OHLC[i][0], OHLC[i][3], OHLC[i][12]])
			
		for i in range(divergence_period_lengths[0], divergence_period_lengths[1]):
			k = 0
			while len(data)-(i+k) > 0:
				day_data = []
				price_data = []
				macd_data = []
				for j in range((len(data)-(i+k)), (len(data)-k)):
					#print(j)
					day_data.append(data[j][0])
					price_data.append(data[j][1])
					macd_data.append(data[j][2])
				
				price_slope = get_slope(price_data)
				macd_slope = get_slope(macd_data)
				if price_slope < 0 and macd_slope > 0 and nr_of_bull_divergences < max_divergences:
					# print("BULL scenario!")
					# print("i=", i, "\t k=", k)
					# print("price_slope:", price_slope)
					# print("macd_slope:", macd_slope)
					# print("start_date:", day_data[0], "end_date:", day_data[-1])
					# print("\n")
					bull_divergences.append([i, price_slope, macd_slope, day_data[0], day_data[-1]])
					nr_of_bull_divergences = nr_of_bull_divergences + 1
					#input("enter...")
				k = k + 1
				
		return bull_divergences
			
	if momentum == 'BEAR':
		data = []
		nr_of_bear_divergences = 0
		for i in range((len(OHLC) - divergence_look_back_period), len(OHLC)):
			data.append([OHLC[i][0], OHLC[i][2], OHLC[i][12]])
	
		for i in range(divergence_period_lengths[0], divergence_period_lengths[1]):
			k = 0
			while len(data)-(i+k) > 0:
				day_data = []
				price_data = []
				macd_data = []
				for j in range((len(data)-(i+k)), (len(data)-k)):
					#print(j)
					day_data.append(data[j][0])
					price_data.append(data[j][1])
					macd_data.append(data[j][2])
				
				price_slope = get_slope(price_data)
				macd_slope = get_slope(macd_data)
				if price_slope > 0 and macd_slope < 0 and nr_of_bear_divergences < max_divergences:
					# print("BEAR scenario!")
					# print("i=", i, "\t k=", k)
					# print("price_slope:", price_slope)
					# print("macd_slope:", macd_slope)
					# print("start_date:", day_data[0], "end_date:", day_data[-1])
					# print("\n")
					bear_divergences.append([i, price_slope, macd_slope, day_data[0], day_data[-1]])
					nr_of_bear_divergences = nr_of_bear_divergences + 1
					#input("enter...")
				k = k + 1
				
		return bear_divergences
		
def calculate_indicators(coin):
	global total_nr_of_coins
	
	data = get_historical_prices(coin)
	
	if len(data['result']) > 100:
		OHLC = []

		for info in data['result']:
			day = info['T']		#type string
			open1 = info['O']	#type float
			high = info['H']
			low = info['L']
			close = info['C']
			volume	= info['V']
			OHLC.append([day, open1, high, low, close, volume])
		
		#removing first data candle, because of incorrect information when first listing on exchange
		del OHLC[0]
		
		williams_R(OHLC, williams_period)
		willy(OHLC, willy_period)
		macd(OHLC, macd_ema1, macd_ema2, macd_signal)
		
		current_coin = coin
		for period in fib_period:
			fib_data = fib(OHLC, period)
			if fib_data != None:
				if fib_data[0] == 'BULL':
					bull_willy = check_willy(OHLC, 'BULL')
					if len(bull_willy) > 0:
						bull_divergences = get_all_slopes(OHLC, 'BULL')
						if len(bull_divergences) > 0:
							if current_coin not in signaled_coins:
								signaled_coins.append(current_coin)
								total_nr_of_coins += 1
								print(coin, ' - BULL RLZ!')
								email_info.write(str(coin) + ' https://bittrex.com/Market/Index?MarketName=BTC-' + str(coin) + '\n')
							print("fib_data:", fib_data)
							
							if current_coin not in prev_signaled_coins:
								email_info.write(str(fib_data[1]) + ' period - ' + 'Bullish - ' + ('%.2f' %(1-fib_data[6])) + ' - NEW SIGNAL!' + '\n')
							else:
								email_info.write(str(fib_data[1]) + ' period - ' + 'Bullish - ' + ('%.2f' %(1-fib_data[6])) + '\n')
							email_info.write('Low on ' + (str(fib_data[2]))[:10] + ' at ' + str(fib_data[3]) + '\n')
							email_info.write('High on '  + (str(fib_data[4]))[:10] + ' at ' + str(fib_data[5]) + '\n')
							
							print("nr of willy values:", len(bull_willy))
							email_info.write(str(len(bull_willy)) + ' Willy values' + '\n')
							# for w in bull_willy:
								# print(w)
							print("nr of divergences:", len(bull_divergences))
							email_info.write(str(len(bull_divergences)) + " MACD divergences" + '\n')
							# for d in bull_divergences:
								# print("length:", d[0], " | price slope: %.3f" %d[1], " | MACD slope: %.3f" %d[2], 
										# " | start_date: ", d[3], " | end_date: ", d[4])
							if stops:
								input("Press Enter to continue...")
							print("\n")
							email_info.write('\n')
				if fib_data[0] == 'BEAR':
					bear_willy = check_willy(OHLC, 'BEAR')
					if len(bear_willy) > 0:
						bear_divergences = get_all_slopes(OHLC, 'BEAR')
						if len(bear_divergences) > 0:
							if current_coin not in signaled_coins:
								signaled_coins.append(current_coin)
								total_nr_of_coins += 1
								print(coin, ' - BEAR RLZ!')
								email_info.write(str(coin) + ' https://bittrex.com/Market/Index?MarketName=BTC-' + str(coin) + '\n')
							print("fib_data:", fib_data)
							
							if current_coin not in prev_signaled_coins:
								email_info.write(str(fib_data[1]) + ' period - ' + 'Bearish - ' + ('%.2f' %fib_data[6]) + ' - NEW SIGNAL!' + '\n')
							else:
								email_info.write(str(fib_data[1]) + ' period - ' + 'Bearish - ' + ('%.2f' %fib_data[6]) + '\n')
							email_info.write('Low on ' + (str(fib_data[2]))[:10] + ' at ' + str(fib_data[3]) + '\n')
							email_info.write('High on '  + (str(fib_data[4]))[:10] + ' at ' + str(fib_data[5]) + '\n')
							
							print("nr of willy values:", len(bear_willy))
							email_info.write(str(len(bear_willy)) + ' Willy values' + '\n')
							# for w in bear_willy:
								# print(w)
							print("nr of divergences:", len(bear_divergences))
							email_info.write(str(len(bear_divergences)) + " MACD divergences" + '\n')
							# for d in bear_divergences:
								# print("length:", d[0], " | price slope: %.3f" %d[1], " | MACD slope: %.3f" %d[2], 
										# " | start_date: ", d[3], " | end_date: ", d[4])
							if stops:
								input("Press Enter to continue...")
							print("\n")
							email_info.write('\n')
		
		# for D in OHLC: print(D)
		
		
		# Values for every item in data
		# day = D[0]
		# open = D[1]
		# high = D[2]
		# low = D[3]
		# close = D[4]
		# volume = D[5]
		# williams_r = D[6]
		# willy = D[7]
		# ema1_for_macd = D[8]
		# ema2_for_macd = D[9]
		# macd_line = D[10]
		# macd_signal_line = D[11]
		# macd_histogram = D[12]

		#for D in OHLC: print(D)
		#log_information(coin, OHLC)

def main():
	global email_info, signaled_coins, prev_signaled_coins
	btc_coins = get_btc_coins()
	#btc_coins = ['AMP', 'AUR', 'ETH', 'LTC', 'NEO', 'OMG', 'TX', 'SYS', 'SNRG']	#LRC
	
	with open('signaled_coins.pkl', 'rb') as input:
		prev_signaled_coins = pickle.load(input)
		
	email_info = open("email_info.txt","w")
	
	print("Starting calculations for: ", len(btc_coins), "coins!")
	
	signaled_coins = []
	for coin in btc_coins:
		try:
			calculate_indicators(coin)
		except Exception as e:
			print(coin, str(e))
	
	new_signaled_coins = []
	for C in signaled_coins:
		if C not in prev_signaled_coins:
			new_signaled_coins.append(C)
			
	print("Total number of signaled coins:", total_nr_of_coins)
	print("New signaled coins:", len(new_signaled_coins), " | ", new_signaled_coins)
	
	email_info.write('\n')
	email_info.write("Total number of Bittrex coins:" + str(len(btc_coins)))
	email_info.write('\n')
	email_info.write("Total number of signaled coins:" + str(len(signaled_coins)) + " | " + str(signaled_coins))
	email_info.write('\n')
	if len(new_signaled_coins) == 0:
		email_info.write("New signaled coins:" + str(len(new_signaled_coins)))
	else:
		email_info.write("New signaled coins:" + str(len(new_signaled_coins)) + " | " + str(new_signaled_coins))
	email_info.close()
	
	email_info = open("email_info.txt","r")
	now = datetime.today() - timedelta(hours=7)
	now = now.strftime("%d-%m-%Y  %H:%M")
	subject = "Coin info " + str(now)
	body = email_info.read()
	SendEmail(subject, body)
	print(signaled_coins)
	
	with open('signaled_coins.pkl', 'wb') as output:
		pickle.dump(signaled_coins, output)
	
if __name__ == "__main__":
	main()