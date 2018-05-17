import requests
import json
from datetime import datetime, timedelta
import sys
import time

from operator import itemgetter

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

window_period = 0.05				#0.1 = 10%, percentage of total periods.
extra_looking_window = 0.02			#0.05 = 5%, percentage of total periods
macd_ema1 = 9
macd_ema2 = 30
macd_signal = 9
divergence_period_lengths = [10, 25]
neg_slope = -0.25
pos_slope = 0.25

bittrex_session = requests.Session()
interval = 'day'

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
				now = datetime.today()
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
		now = datetime.today()
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
		now = datetime.today()
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
	
def create_OHLC(coin):
	data = get_historical_prices(coin, interval)
	OHLC = []
	for info in data['result']:
		day = info['T']		
		day = datetime.strptime(day, '%Y-%m-%dT%H:%M:%S')	#type datetime
		open1 = info['O']	#type float
		high = info['H']
		low = info['L']
		close = info['C']
		volume	= info['V']
		
		period_info = {}
		period_info['day'] = day
		period_info['open'] = open1
		period_info['high'] = high
		period_info['low'] = low
		period_info['close'] = close
		period_info['volume'] = volume
		OHLC.append(period_info)
	#removing first data candle, because of incorrect information when first listing on exchange
	del OHLC[0]
	return OHLC
	
def find_windows(OHLC):
	
	def find_min_and_max(OHLC, start_period, end_period):
		min_price = 99999999999
		max_price = 0
		OHLC_to_test = OHLC[start_period:end_period]
		for D in OHLC_to_test:
			if D['low'] < min_price:
				min_price = D['low']
				min_price_date = D['day']
			if D['high'] > max_price:
				max_price = D['high']
				max_price_date = D['day']
		return min_price, min_price_date, max_price, max_price_date
		
	def find_new_min(OHLC, start_period, end_period):
		min_price = 99999999999
		OHLC_to_test = OHLC[start_period:end_period]
		for D in OHLC_to_test:
			if D['low'] < min_price:
				min_price = D['low']
				min_price_date = D['day']
		return min_price, min_price_date
		
	def find_new_max(OHLC, start_period, end_period):
		max_price = 0
		OHLC_to_test = OHLC[start_period:end_period]
		for D in OHLC_to_test:
			if D['high'] > max_price:
				max_price = D['high']
				max_price_date = D['day']
		return max_price, max_price_date
		
	found_windows = []
	partial_windows = []
	w_period = int(len(OHLC) * window_period)
	A = 0
	B = w_period
	while True:
		partial_windows.append([A, B])
		A = A + w_period
		B = B + w_period
		if B >= len(OHLC):
			B = len(OHLC)
			partial_windows.append([A, B])
			break
	#print(partial_windows)
	
	extra_period = int(len(OHLC) * extra_looking_window)
	print('period length:', w_period)
	print('extra period:', extra_period)
	
	def inner_window(start_period, end_period):
		min_price, min_price_date, max_price, max_price_date = find_min_and_max(OHLC, start_period, end_period)
		if min_price_date < max_price_date:
			while start_period - extra_period > 0:
				start_period = start_period - extra_period
				new_min_price, new_min_date = find_new_min(OHLC, start_period, (start_period + extra_period))
				if new_min_price > min_price:
					break
				else:
					min_price = new_min_price
					min_price_date = new_min_date
			while end_period + extra_period < len(OHLC):
				end_period = end_period + extra_period
				new_max_price, new_max_date = find_new_max(OHLC, (end_period - extra_period), end_period)
				if new_max_price < max_price:
					break
				else:
					max_price = new_max_price
					max_price_date = new_max_date
			if len(found_windows) == 0:
				#print("found first window", [min_price, min_price_date, max_price, max_price_date])
				found_windows.append([min_price, min_price_date, max_price, max_price_date])
				#print("Window:", min_price, min_price_date, max_price, max_price_date)
			if len(found_windows) > 0:
				#print("found window", [min_price, min_price_date, max_price, max_price_date])
				#if min_price_date != found_windows[-1][1]:
				found_windows.append([min_price, min_price_date, max_price, max_price_date])
					#print("Window:", min_price, min_price_date, max_price, max_price_date)
					
			for i in range(len(OHLC)):
				if OHLC[i]['day'] == max_price_date:
					max_price_poz = i
					break
			return max_price_poz
		else:
			return end_period
	
	start_period = 0
	end_period = start_period + w_period
	while (end_period + w_period) < len(OHLC):
		#print("searching window between:", start_period, end_period, ' | ', OHLC[start_period]['day'], ' - ', OHLC[end_period]['day'])
		start_period = inner_window(start_period, end_period) + 1
		end_period = start_period + w_period
		
	return found_windows

def macd(OHLC, macd_ema1, macd_ema2, macd_signal):
	ema1_multiplier = 2 / (macd_ema1 + 1)
	ema2_multiplier = 2 / (macd_ema2 + 1)
	signal_multiplier = 2 / (macd_signal + 1)
	
	for i in range(0, len(OHLC)):
		if i == 0:
			ema1_for_macd = OHLC[i]['close']
			ema2_for_macd = OHLC[i]['close']
			macd_line = 0
			macd_signal_line = 0
			macd_histogram = 0
		elif i == 1:
			ema1_for_macd = (OHLC[i]['close'] - OHLC[i-1]['macd ema1']) * ema1_multiplier + OHLC[i-1]['macd ema1']
			ema2_for_macd = (OHLC[i]['close'] - OHLC[i-1]['macd ema2']) * ema2_multiplier + OHLC[i-1]['macd ema2']
			macd_line = ema1_for_macd - ema2_for_macd
			macd_signal_line = macd_line
			macd_histogram = macd_line - macd_signal_line
		elif i > 1:
			ema1_for_macd = (OHLC[i]['close'] - OHLC[i-1]['macd ema1']) * ema1_multiplier + OHLC[i-1]['macd ema1']
			ema2_for_macd = (OHLC[i]['close'] - OHLC[i-1]['macd ema2']) * ema2_multiplier + OHLC[i-1]['macd ema2']
			macd_line = ema1_for_macd - ema2_for_macd
			macd_signal_line = (macd_line - OHLC[i-1]['macd line']) * signal_multiplier + OHLC[i-1]['macd line']
			macd_histogram = macd_line - macd_signal_line
		OHLC[i]['macd ema1'] = ema1_for_macd
		OHLC[i]['macd ema2'] = ema2_for_macd
		OHLC[i]['macd line'] = macd_line
		OHLC[i]['macd signal'] = macd_signal_line
		OHLC[i]['macd histogram'] = macd_histogram	

def find_divergence(OHLC, window):
	
	def max_and_min(list):
		maximum = max(list)
		minimum = min(list)
		return maximum, minimum	
	
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
	
	data = []
	nr_of_bull_divergences = 0
	for i in range(0, len(OHLC)):
		if window[3] == OHLC[i]['day']:
			start_period = i + 1
	print("start_period:", start_period)
	#input("enter...")
		
	for i in range(divergence_period_lengths[0], divergence_period_lengths[1]):
		k = 0
		while (len(OHLC)-start_period-(i+k) > 0) and (k < 30):
			day_data = []
			price_data = []
			macd_data = []
			for j in range(start_period, start_period+(i+k)):
				#print(j)
				day_data.append(OHLC[j]['day'])
				price_data.append(OHLC[j]['close'])
				macd_data.append(OHLC[j]['macd histogram'])
			
			#print("length:", len(price_data))
			#print("i=", i, "\t k=", k)
			price_slope = get_slope(price_data)
			macd_slope = get_slope(macd_data)
			#print("price_slope:", price_slope)
			#print("macd_slope:", macd_slope)
			if price_slope < neg_slope and macd_slope > pos_slope:# and nr_of_bull_divergences < max_divergences:
				# print("BULL scenario!")
				#print("i=", i, "\t k=", k)
				# print("price_slope:", price_slope)
				# print("macd_slope:", macd_slope)
				# print("start_date:", day_data[0], "end_date:", day_data[-1])
				# print("\n")
				bull_divergences.append([i, price_slope, macd_slope, day_data[0], day_data[-1]])
				nr_of_bull_divergences += 1
				#input("enter...")
			k = k + 1
		
	#print(bull_divergences)
	return bull_divergences
		
#btc_coins = get_btc_coins()
btc_coins = ['TRX', 'LTC', 'DOGE', 'NEO', 'ADA']

for C in btc_coins:
	OHLC = create_OHLC(C)
	if len(OHLC) > 100:
		macd(OHLC, macd_ema1, macd_ema2, macd_signal)
		# for F in OHLC:
			# print(F)
		print(C, ' - ', len(OHLC))
		found_windows = find_windows(OHLC)
		for W in found_windows:
			divergences = find_divergence(OHLC, W)
			print("Window:", W)
			print("divergences =", len(divergences))
		print("\n")