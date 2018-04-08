#!/usr/bin/env python3

# pip3 install -r requirements.txt
from datetime import date, datetime, timedelta
from time import sleep
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import dates as mdates
from os import path
import argparse, json, requests, sys

# MeetUp API Specification
# https://www.meetup.com/meetup_api/

base_url = 'https://api.meetup.com/'

def getGroupID(group_urlname):
	response = requests.get('{}{}'.format(base_url, group_urlname))
	if response.status_code != 200:
		print(response.status_code)
		print(response.headers)
		print(response.text)
		sys.exit(1)
	response = response.json()
	return response['id']

def getMembers(api_key, group_id, verbose=False):
	payload = {'group_id': group_id, 'key': api_key, 'order': 'joined', 'desc': 'true'}
	response = requests.get('{}2/members'.format(base_url), params=payload)
	#print(response.headers)
	if verbose:
		checkRateLimit(response.headers)
	if response.status_code != 200:
		print(response.status_code)
		print(response.text)
		print(response.headers)
		sys.exit(1)

	response = response.json()
	meta = response['meta']
	members = response['results']

	if meta['count'] == meta['total_count']:
		if verbose:
			print('Retrieved {} members'.format(len(members)), file=sys.stderr)
		return members

	while len(members) < meta['total_count'] and meta['next'] != '':
		if verbose:
			print('Retrieved {} members'.format(len(members)), file=sys.stderr)
		next_page = meta['next']
		# TODO: verbose logging
		#print(next_page)
		response = requests.get(next_page)
		if verbose:
			print(response.status_code)
		if verbose:
			checkRateLimit(response.headers)
		if response.status_code != 200:
			print(response.headers)
			print(response.text)
		response = response.json()

		meta = response['meta']
		next_members = response['results']
		members.extend(next_members)

	if verbose:
		print('Retrieved {} members'.format(len(members)), file=sys.stderr)
	return members

def saveMembers(members, filename):
	with open(path.join('data', filename), 'w') as f:
		json.dump(members, fp=f)

def updateMembers(api_key, group_id, filename, verbose=False):
	members = getMembers(api_key, group_id, verbose=verbose)
	saveMembers(members, filename)

def checkRateLimit(headers):
	print('{}/{} requests left in quota. Reset in {} seconds.'.format(headers.get('X-RateLimit-Remaining'), headers.get('X-RateLimit-Limit'), headers.get('X-RateLimit-Reset')), file=sys.stderr)

def joinedHist(members):
	fig, ax = plt.subplots(1,1, figsize=(12,6), dpi=100)
	joined_dates = np.array([int(member['joined']) / 1000 for member in members])
	start = datetime.fromtimestamp(np.amin(joined_dates))
	now = datetime.now()
	joined_dates = mdates.epoch2num(joined_dates)
	months = [datetime(year=y,month=m,day=1) \
		for y in range(start.year,now.year+1) \
		for m in range(1,13) \
		if not ((y == now.year and m > now.month+1) or \
			(y == start.year and m < start.month))]
	bins = mdates.date2num(months)

	hist, _ = np.histogram(joined_dates, bins=bins)
	labels = [m.strftime('%b-%y') if m.month % 6 == 1 else '' for m in months]
	labels = np.array(labels)

	plt.xticks(bins, labels)
	ax.bar(range(len(hist)), hist, width=0.8, align='center', tick_label=labels[:-1], zorder=3)

	ax.yaxis.grid(which='major', linestyle='--', zorder=0)
	ax.set_ylabel('Members')
	ax.set_title('Joined MeetUp')

	timestamp = datetime.now().isoformat(timespec='minutes')
	plt.savefig(path.join('output', '{}-joined-meetup-{}.png'.format(group_urlname, timestamp)))

def activeHist(members):
	fig, ax = plt.subplots(1,1, figsize=(12,6), dpi=100)
	visited_dates = np.array([int(member['visited']) / 1000 for member in members])
	visited_dates = mdates.epoch2num(visited_dates)
	now = datetime.now()
	start = now - timedelta(days=52*7)

	months = [datetime(year=y,month=m,day=1) \
		for y in range(start.year,now.year+1) \
		for m in range(1,13) \
		if not ((y == now.year and m > now.month+1) or \
			(y == start.year and m < start.month))]
	bins = mdates.date2num(months)

	hist, _ = np.histogram(np.clip(visited_dates, bins[0], bins[-1]), bins=bins)

	labels = [m.strftime('%b-%y') for m in months]
	labels[0] = '<' + labels[0]
	labels = np.array(labels)
	plt.xticks(bins, labels)
	ax.bar(range(len(hist)), hist, width=0.8, align='center', tick_label=labels[:-1], zorder=3)
	ax.yaxis.grid(which='major', linestyle='--', zorder=0)
	ax.set_ylabel('Members')
	ax.set_title('Last Visited MeetUp')

	timestamp = datetime.now().isoformat(timespec='minutes')
	plt.savefig(path.join('output', '{}-visited-meetup-{}.png'.format(group_urlname, timestamp)))

def loadMembers(filename):
	with open(path.join('data', filename), 'r') as f:
		members = json.load(f)
	return members

def generateCharts(members):
	raw_count = len(members)
	members = [member for member in members if ('joined' in member) and ('visited' in member)]
	if len(members) != raw_count:
		print('Filtered out {} member(s)'.format(raw_count - len(members)))

	joinedHist(members)
	activeHist(members)

def getNewMembers(members, last=None):
	raw_count = len(members)
	members = [member for member in members if 'joined' in member]
	if len(members) != raw_count:
		print('Filtered out {} member(s)'.format(raw_count - len(members)))
	members = sorted(members, key=lambda member : member['joined'], reverse=True)

	if not last:
		print('Returning last 10 members')
		return members[:10][::-1]

	print('Returning members since {}'.format(last))
	for i, member in enumerate(members):
		if member.get('id') == last:
			last_index = i
			break
	return members[:last_index][::-1]

def printMembers(members):
	raw_count = len(members)
	members = [member for member in members if ('joined' in member) and ('visited' in member)]
	if len(members) != raw_count:
		print('Filtered out {} member(s)'.format(raw_count - len(members)))
	if len(members) == 0:
		return
	for member in members:
		joined = datetime.fromtimestamp(int(member['joined']) / 1000)
		visited = datetime.fromtimestamp(int(member['visited']) / 1000)
		print('{0: <24}{1: <12}'.format(member['name'], str(joined)))

if __name__ == '__main__':
	# TODO: API key file argument

	parser = argparse.ArgumentParser()
	parser.add_argument('group')
	parser.add_argument('-d', '--daemon', help='Check daily', action='store_true')
	parser.add_argument('-v', '--verbose', help='Print update progress', action='store_true')
	args = parser.parse_args()

	with open('api-key.txt') as f:
		api_key = f.read().strip()

	group_urlname = args.group
	group_id = getGroupID(group_urlname)
	timestamp = datetime.now().isoformat(timespec='seconds')
	filename = '{}-results-{}.json'.format(group_urlname, timestamp)

	updateMembers(api_key, group_id, filename, verbose=args.verbose)

	members = loadMembers(filename)

	print('Read {} members'.format(len(members)))

	if args.daemon:
		new_members = getNewMembers(members)
		printMembers(new_members)
		last_id = new_members[-1].get('id')
		last_check = datetime.now()
		while True:
			if (datetime.now() - last_check) < timedelta(hours=6):
				sleep(60 * 15)
				continue

			last_check = datetime.now()
			timestamp = datetime.now().isoformat(timespec='seconds')
			print('Checking for new members at ' + timestamp, file=sys.stderr)
			filename = '{}-results-{}.json'.format(group_urlname, timestamp)
			updateMembers(api_key, group_id, filename, verbose=args.verbose)
			members = loadMembers(filename)

			new_members = getNewMembers(members, last=last_id)
			if len(new_members) > 0:
				printMembers(new_members)
				last_id = new_members[-1].get('id')


	else:
		generateCharts(members)
