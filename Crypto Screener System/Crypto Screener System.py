import requests
import json
from datetime import datetime, timedelta
import time
import sys
import pandas as pd
import talib
from operator import itemgetter
from scipy.stats import linregress

bittrex_session = requests.Session()
interval = 'day'

pd.options.display.float_format = '{:,.8f}'.format
pd.set_option('display.max_columns', 10)
pd.set_option('display.width', 1000)

macd_ema1 = 9
macd_ema2 = 30
macd_signal = 9

williams_period = 21
willy_period = 13

w_lookback_periods = [5, 10, 15]

divergence_lookback_periods = [5, 25]

rlz_periods = [50, 75, 100, 125, 150, 175, 200]

poz_slope = 0.5
neg_slope = -0.5

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
	count = 0
	while True:
		response = bittrex_session.get(url)
		data = json.loads(response.text)
		if (data != None) and (data['success'] == True) and (data['result'] != None):
			break
		else:
			count += 1
			time.sleep(1)
			if count == 5:
				sys.exit()
	return data['result']
	
def create_OHLC(coin):
	data = get_historical_prices(coin, interval)

	OHLC = []
	for info in data:
		day = info['T']		
		day = datetime.strptime(day, '%Y-%m-%dT%H:%M:%S')	#type datetime
		open1 = info['O']	#type float
		high = info['H']
		low = info['L']
		close = info['C']
		volume	= info['V']
		
		period_info = {}
		period_info['date'] = day
		period_info['open'] = open1
		period_info['high'] = high
		period_info['low'] = low
		period_info['close'] = close
		period_info['volume'] = volume
		OHLC.append(period_info)
	#removing first data candle, because of incorrect information when first listing on exchange
	del OHLC[0]	
	
	OHLCV = pd.DataFrame(OHLC)
	OHLCV = OHLCV[['date', 'open', 'high', 'low', 'close', 'volume']]
	OHLCV.set_index('date', inplace=True)
	
	return OHLCV

def MACD(OHLCV):
	OHLCV['macd'], OHLCV['macdsignal'], OHLCV['macdhist'] = talib.MACD(OHLCV['close'], fastperiod=macd_ema1, slowperiod=macd_ema2, signalperiod=macd_signal)
	return OHLCV
	
def WILLR(OHLCV):
	OHLCV['w%r'] = talib.WILLR(OHLCV['high'], OHLCV['low'], OHLCV['close'], timeperiod=williams_period)
	OHLCV['willy'] = talib.EMA(OHLCV['w%r'], timeperiod=willy_period)
	return OHLCV

def write_to_excel(coin, OHLCV):
	file_name = coin + '_OHLCV.xlsx'
	writer = pd.ExcelWriter(file_name, engine='xlsxwriter')
	OHLCV.to_excel(writer, sheet_name='Sheet1')
	writer.save()
	
def find_min(temp_df):
	min_date = temp_df['low'].idxmin()
	return min_date
	
def find_max(temp_df):
	max_date = temp_df['high'].idxmax()
	return max_date

def RLZ(OHLCV, period):
	extra_look_period = int(period*0.1)
	rlz_period_type = 'rlz_' + str(period) + '_type'
	rlz_period_low_date = 'rlz_' + str(period) + '_low_date'
	rlz_period_low_value = 'rlz_' + str(period) + '_low_value'
	rlz_period_high_date = 'rlz_' + str(period) + '_high_date'
	rlz_period_high_value = 'rlz_' + str(period) + '_high_value'
	rlz_period_fib = 'rlz_' + str(period) + '_fib'
	
	for i in range(period, len(OHLCV)):
		temp_df = OHLCV[i-period : i]
		
		max_date = find_max(temp_df)
		max_date_value = temp_df.get_value(max_date, 'high')
		
		min_date = find_min(temp_df)
		min_date_value = temp_df.get_value(min_date, 'low')
		
		current_close = temp_df.get_value(temp_df.index[-1], 'close')
		
		if max_date > min_date:
			OHLCV.set_value(OHLCV.index[i], rlz_period_type, 'bull')
			k = 1
			while True:
				location_min_date = temp_df.index.get_loc(min_date)
				if (location_min_date <= k*extra_look_period) and (i - period - k*extra_look_period > 0):
					temp_df = OHLCV[i-period-k*extra_look_period : i]
					new_min_date = find_min(temp_df)
					if new_min_date == min_date:
						break
					elif new_min_date < min_date:
						min_date = new_min_date
						min_date_value = temp_df.get_value(min_date, 'low')
						k += 1
				else:
					break
			OHLCV.set_value(OHLCV.index[i], rlz_period_low_date, min_date)
			OHLCV.set_value(OHLCV.index[i], rlz_period_low_value, min_date_value)
			
			OHLCV.set_value(OHLCV.index[i], rlz_period_high_date, max_date)
			OHLCV.set_value(OHLCV.index[i], rlz_period_high_value, max_date_value)
			
			OHLCV.set_value(OHLCV.index[i], rlz_period_fib, (max_date_value - current_close) / (max_date_value - min_date_value))	
		else:
			OHLCV.set_value(OHLCV.index[i], rlz_period_type, 'bear')
			k = 1
			while True:
				location_max_date = temp_df.index.get_loc(max_date)
				if (location_max_date <= k*extra_look_period) and (i - period - k*extra_look_period > 0):
					temp_df = OHLCV[i-period-k*extra_look_period : i]
					new_max_date = find_max(temp_df)
					if new_max_date ==  max_date:
						break
					elif new_max_date < max_date:
						max_date = new_max_date
						max_date_value = temp_df.get_value(max_date, 'high')
						k += 1
				else:
					break
					
			OHLCV.set_value(OHLCV.index[i], rlz_period_low_date, min_date)
			OHLCV.set_value(OHLCV.index[i], rlz_period_low_value, min_date_value)
			
			OHLCV.set_value(OHLCV.index[i], rlz_period_high_date, max_date)
			OHLCV.set_value(OHLCV.index[i], rlz_period_high_value, max_date_value)
			
			OHLCV.set_value(OHLCV.index[i], rlz_period_fib, ((current_close - min_date_value) / (max_date_value - min_date_value)))

	return OHLCV
	
def W_finder(OHLCV):	
	for i in range(max(w_lookback_periods), len(OHLCV)):
		Ws = []
		for period in w_lookback_periods:		
			temp_df = OHLCV[i - period : i]
			point_B_date = temp_df['close'].idxmin()
			point_B_value = temp_df.get_value(point_B_date, 'close')
			point_B_location = temp_df.index.get_loc(point_B_date)
			
			if len(temp_df) - point_B_location < 2:
				continue
			
			temp_df2 = temp_df[point_B_location+1:len(temp_df)]
			point_D_date = temp_df2['close'].idxmin()
			point_D_value = temp_df2.get_value(point_D_date, 'close')
			point_D_location = temp_df.index.get_loc(point_D_date)
			
			if (point_D_location - point_B_location == 1):
				if len(temp_df) - point_D_location < 2:
					continue
				else:
					temp_df3 = temp_df[point_D_location+1:len(temp_df)]
					point_D_date = temp_df3['close'].idxmin()
					point_D_value = temp_df3.get_value(point_D_date, 'close')
					point_D_location = temp_df.index.get_loc(point_D_date)
			
			if point_D_value < point_B_value:
				print(temp_df)
				print(temp_df2)
				print('point_B_date:', point_B_date, point_B_value)
				print('point_D_date:', point_D_date, point_D_value)
				input('enter...')
			
			df_for_point_C = temp_df[point_B_location+1:point_D_location]
			point_C_date = df_for_point_C['close'].idxmax()
			point_C_value = df_for_point_C.get_value(point_C_date, 'close')
			point_C_location = temp_df.index.get_loc(point_C_date)
			
			if point_C_value < point_D_value:
				continue
				
			if (point_B_value == point_D_value) or (point_B_value == point_C_value) or (point_C_value == point_D_value):
				continue
				
			if len(temp_df) - point_D_location < 2:
				continue
			
			df_for_point_E = temp_df[point_D_location+1:len(temp_df)]
			point_E_dates = df_for_point_E['close'][df_for_point_E['close'] > point_C_value].index
			if len(point_E_dates) == 0:
				continue
			elif len(point_E_dates) > 0:
				point_E_date = point_E_dates[0]
			point_E_value = df_for_point_E.get_value(point_E_date, 'close')
			point_E_location = temp_df.index.get_loc(point_E_date)
			
			if point_E_value < point_C_value:
				continue
			
			score_of_levels_B_and_D = 0.6 * (point_B_value/point_D_value)**10 # as more near these two point is better. Point B always is lower than point D
			periods_from_B_to_C = point_C_location - point_B_location
			periods_from_C_to_D = point_D_location - point_C_location
			simmetry = min(periods_from_B_to_C, periods_from_C_to_D) / max(periods_from_B_to_C, periods_from_C_to_D) * 0.4

			Total_Score = score_of_levels_B_and_D  + simmetry
			
			Ws.append({'point_B_date' : point_B_date, 
						'point_B_value' : point_B_value, 
						'point_C_date' : point_C_date, 
						'point_C_value' : point_C_value, 
						'point_D_date' : point_D_date, 
						'point_D_value' : point_D_value,
						'point_E_date' : point_E_date, 
						'point_E_value' : point_E_value,
						'Total_Score' : Total_Score})
		
		if len(Ws) == 0:
			continue
		elif len(Ws) == 1:
			OHLCV.set_value(OHLCV.index[i], 'w_price_score', Ws[0]['Total_Score'])
			
			OHLCV.set_value(OHLCV.index[i], 'w_price_B_date', Ws[0]['point_B_date'])
			OHLCV.set_value(OHLCV.index[i], 'w_price_B_value', Ws[0]['point_B_value'])
			
			OHLCV.set_value(OHLCV.index[i], 'w_price_C_date', Ws[0]['point_C_date'])
			OHLCV.set_value(OHLCV.index[i], 'w_price_C_value', Ws[0]['point_C_value'])
			
			OHLCV.set_value(OHLCV.index[i], 'w_price_D_date', Ws[0]['point_D_date'])
			OHLCV.set_value(OHLCV.index[i], 'w_price_D_value', Ws[0]['point_D_value'])
			
			OHLCV.set_value(OHLCV.index[i], 'w_price_E_date', Ws[0]['point_E_date'])
			OHLCV.set_value(OHLCV.index[i], 'w_price_E_value', Ws[0]['point_E_value'])
		elif len(Ws) > 1:
			sorted_Ws = sorted(Ws, key=itemgetter('Total_Score'), reverse=True)
			OHLCV.set_value(OHLCV.index[i], 'w_price_score', Ws[0]['Total_Score'])
			
			OHLCV.set_value(OHLCV.index[i], 'w_price_B_date', Ws[0]['point_B_date'])
			OHLCV.set_value(OHLCV.index[i], 'w_price_B_value', Ws[0]['point_B_value'])
			
			OHLCV.set_value(OHLCV.index[i], 'w_price_C_date', Ws[0]['point_C_date'])
			OHLCV.set_value(OHLCV.index[i], 'w_price_C_value', Ws[0]['point_C_value'])
			
			OHLCV.set_value(OHLCV.index[i], 'w_price_D_date', Ws[0]['point_D_date'])
			OHLCV.set_value(OHLCV.index[i], 'w_price_D_value', Ws[0]['point_D_value'])
			
			OHLCV.set_value(OHLCV.index[i], 'w_price_E_date', Ws[0]['point_E_date'])
			OHLCV.set_value(OHLCV.index[i], 'w_price_E_value', Ws[0]['point_E_value'])
			
	return OHLCV

def find_divergence(OHLCV):
	def normalize(x):
		max_x, min_x = max_and_min(x)
		new_x = []	
		for i in range(0, len(x)):
			z = (x[i]-min_x)/(max_x-min_x)
			new_x.append(z)
		return new_x

	def max_and_min(list):
		maximum = max(list)
		minimum = min(list)
		return maximum, minimum	
	
	#start_period finds the location of the first macdhist value
	start_period = OHLCV.index.get_loc(OHLCV['macdhist'].first_valid_index())

	for i in range(start_period+divergence_lookback_periods[1], len(OHLCV)):
		bull_divergences = []
		for k in range(divergence_lookback_periods[0], divergence_lookback_periods[1]):
			day_data = []
			price_data = []
			macd_data = []
			j_data = []
			
			for j in range(i-k, i):
				day_data.append(OHLCV.ix[j].name)
				price_data.append(OHLCV.ix[j]['close'])
				macd_data.append(OHLCV.ix[j]['macdhist'])
				j_data.append(j)
			
			price_data = normalize(price_data)
			macd_data = normalize(macd_data)
			
			price_slope, price_intercept, price_rvalue, price_pvalue, price_stderr = linregress(j_data, price_data)
			macd_slope, macd_intercept, macd_rvalue, macd_pvalue, macd_stderr = linregress(j_data, macd_data)
			
			new_price_slope = price_slope * len(j_data)
			new_macd_slope = macd_slope * len(j_data)

			if new_price_slope < neg_slope and new_macd_slope > poz_slope:				
				bull_divergences.append({'Divergence Start' : day_data[0], 
										'Divergence End' : day_data[-1], 
										'Price Slope' : price_slope, 
										'MACD Slope' : macd_slope})
				break

		if len(bull_divergences) > 0:
			OHLCV.set_value(OHLCV.index[i], 'divergence', len(bull_divergences))
			
	return OHLCV

def willy_condition(df, value):
	for i in range(0,len(df)):
		if df[i] < value:
			return True
	return False
	
def w_condition(df, value):
	for i in range(0,len(df)):
		if df[i] > value:
			return True
	return False
	
def divergence_condition(df, value):
	for i in range(0,len(df)):
		if df[i] > value:
			return True
	return False

def main():
	btc_coins = get_btc_coins()
	to_remove = ['LGD']
	for R in to_remove:
		btc_coins.remove(R)

	#btc_coins = ['ADA', 'NEO']
	signals = []

	for C in btc_coins:
		OHLCV = create_OHLC(C)
		if len(OHLCV) < 220:
			continue
			
		print(C, len(OHLCV), 'days')
		
		start_time = time.time()
		OHLCV = MACD(OHLCV)
		print("Creating MACD data--- %s seconds ---" % (time.time() - start_time))
		
		start_time = time.time()
		OHLCV = WILLR(OHLCV)
		print("Creating Willy data--- %s seconds ---" % (time.time() - start_time))
		
		start_time = time.time()
		for p in rlz_periods:
			OHLCV = RLZ(OHLCV, p)
		print("Creating 3 RLZ data--- %s seconds ---" % (time.time() - start_time))
		
		start_time = time.time()
		OHLCV = W_finder(OHLCV)
		print("Creating W data--- %s seconds ---" % (time.time() - start_time))
		
		start_time = time.time()
		OHLCV  = find_divergence(OHLCV)
		print("Creating Divergence data--- %s seconds ---" % (time.time() - start_time))
		
		print("Writing to excel")
		write_to_excel(C, OHLCV)
		print("Done for %s !" %C)
		print('\n')
		
if __name__ == "__main__":
	main()