import time
import sys
import logging
from logging.handlers import RotatingFileHandler
from getSongInfo import getSongInfo
import requests
from io import BytesIO
from PIL import Image
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
import os
import configparser
from datetime import datetime, timedelta
import schedule


def main() -> int:
	query = {
		'lat': '12.345678', 'lon': '9.123456', 'units': 'metric', 'exclude': 'minutely,alerts',
		'appid': 'xxx'}
	response = requests.get("https://api.openweathermap.org/data/2.5/onecall", params=query, timeout=5)
	response_json = response.json()
	last_refresh = datetime.now()

	def refresh_weather():
		response = requests.get("https://api.openweathermap.org/data/2.5/onecall", params=query, timeout=5)
		nonlocal response_json
		response_json = response.json()
		return response_json

	black_img = Image.new('RGBA', (16, 16)).convert('RGBA')
	iconMap = {
		'01d': 'sun.png',
		'01n': 'half-moon.png',
		'02d': 'cloudy_2.png',
		'02n': 'cloudy-night.png',
		'03d': 'cloud.png',
		'03n': 'cloud.png',
		'04d': 'cloudy_broken.png',
		'04n': 'cloudy_broken.png',
		'09d': 'rain_shower.png',
		'09n': 'rain_shower.png',
		'10d': 'rain.png',
		'10n': 'rain.png',
		'11d': 'storm.png',
		'11n': 'storm_1.png',
		'13d': 'snowflake.png',
		'13n': 'snowflake.png',
		'50d': 'wind.png',
		'50n': 'wind.png'}

	def getIcon(icon_name):
		icon_path = iconMap[icon_name]
		if not icon_path:
			icon_path = 'thunder.png'
		return Image.alpha_composite(black_img, Image.open(os.path.join(dir, '../wheather_icons/' + icon_path)).convert(
			'RGBA')).convert('RGB')

	username = sys.argv[1]
	token_path = sys.argv[2]

	# Configuration file
	dir = os.path.dirname(__file__)
	filename = os.path.join(dir, '../config/rgb_options.ini')

	# Configures logger for storing song data
	logging.basicConfig(
		format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename='spotipy.log', level=logging.INFO)
	logger = logging.getLogger('spotipy_logger')

	# automatically deletes logs more than 2000 bytes
	handler = RotatingFileHandler('spotipy.log', maxBytes=2000, backupCount=3)
	logger.addHandler(handler)

	# Configuration for the matrix
	config = configparser.ConfigParser()
	config.read(filename)

	options = RGBMatrixOptions()
	options.rows = int(config['DEFAULT']['rows'])
	options.cols = int(config['DEFAULT']['columns'])
	options.chain_length = int(config['DEFAULT']['chain_length'])
	options.parallel = int(config['DEFAULT']['parallel'])
	options.hardware_mapping = config['DEFAULT']['hardware_mapping']
	options.gpio_slowdown = int(config['DEFAULT']['gpio_slowdown'])
	options.brightness = int(config['DEFAULT']['brightness'])
	options.led_rgb_sequence = config['DEFAULT']['led_rgb_sequence']

	font = graphics.Font()
	font_small = graphics.Font()
	font_path = os.path.join(dir, '../fonts/5x8.bdf')
	font_small_path = os.path.join(dir, '../fonts/4x6.bdf')
	print(font_path)
	font.LoadFont(font_path)
	font_small.LoadFont(font_small_path)

	# schedule.every(5).minutes.do(refresh_weather)
	text_color = graphics.Color(240, 230, 220)
	default_image = os.path.join(dir, config['DEFAULT']['default_image'])
	print(default_image)
	matrix = RGBMatrix(options=options)
	canvas = matrix.CreateFrameCanvas()
	lastURL = ""
	try:
		while True:
			try:
				imageURL = getSongInfo(username, token_path)[1]
				if imageURL is not None:
					if imageURL == lastURL:
						time.sleep(1)
						continue
					lastURL = imageURL
					response_image = requests.get(imageURL)
					image = Image.open(BytesIO(response_image.content))
					image.thumbnail((matrix.width, matrix.height), Image.ANTIALIAS)
					# image.thumbnail((matrix.width/2, matrix.height/2), Image.ANTIALIAS)
					canvas.SetImage(image.convert('RGB'))
					time.sleep(1)
				else:
					main_icon_name = response_json['current']['weather'][0]['icon']
					main_icon = getIcon(main_icon_name)
					now = datetime.now()
					if now - last_refresh > timedelta(minutes=5):
						response_json = refresh_weather()
						last_refresh = now
						print('refreshed')
					now_text = now.strftime('%H:%M')
					secs_text = now.strftime(':%S')
					secs = int(now.strftime('%-S'))
					length = graphics.DrawText(canvas, font, 0, 8, text_color, now_text)
					graphics.DrawText(
						canvas, font, 10, 16,
						graphics.Color((int(secs * 4.25) + 125) % 255, 255 - int(secs * 4.25) % 255, int(secs * 4.25) % 255),
						secs_text)
					canvas.SetImage(main_icon, length, 0)
					graphics.DrawText(
						canvas, font_small, length + 18, 8, text_color, str(response_json['current']['temp']) + '°')
					graphics.DrawText(
						canvas, font_small, length + 18, 16, text_color, str(response_json['current']['humidity']) + '%')
					for i in range(1, 5):
						icon_name = response_json['hourly'][i]['weather'][0]['icon']
						time_text = datetime.fromtimestamp(response_json['hourly'][i]['dt']).strftime('%Hh')
						canvas.SetImage(getIcon(icon_name), 16 * (i - 1), 16)
						graphics.DrawText(canvas, font_small, 16 * (i - 1) + 2, 40 - 2, text_color, time_text)
						icon_name_daily = response_json['daily'][i]['weather'][0]['icon']
						time_text_daily = datetime.fromtimestamp(response_json['daily'][i]['dt']).strftime('%a')
						canvas.SetImage(getIcon(icon_name_daily), 16 * (i - 1), 40)
						graphics.DrawText(canvas, font_small, 16 * (i - 1) + 2, 64 - 2, text_color, time_text_daily)
					time.sleep(0.5)
				# canvas.SetImage(image.convert('RGB'), matrix.width/2, matrix.height/2)
				canvas = matrix.SwapOnVSync(canvas)
				# time.sleep(1)
				canvas.Clear()
			except Exception as e:
				print(str(e))
				graphics.DrawText(canvas, font_small, 0, 32, text_color, str(e))
				image = Image.open(default_image)
				image.thumbnail((matrix.width, matrix.height), Image.ANTIALIAS)
				canvas.SetImage(image.convert('RGB'))
				canvas = matrix.SwapOnVSync(canvas)
				time.sleep(1)
				canvas.Clear()
	except KeyboardInterrupt:
		return 0
	return 0


if len(sys.argv) > 2:
	if __name__ == '__main__':
		sys.exit(main())
else:
	print("Usage: %s username" % (sys.argv[0],))
	sys.exit()
