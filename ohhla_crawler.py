#!/usr/bin/python3

import os
import sys
import csv
import requests
import argparse
from bs4 import BeautifulSoup


ohhla_pages_all_cache = {}
ohhla_artist_cache = {}

def warning(*objs):
    print("WARNING: ", *objs, file=sys.stderr)
    # print("WARNING: ", *objs)

# http://stackoverflow.com/a/3668771
def meta_redirect(soup):

    result = soup.find("meta", {"http-equiv": "Refresh"})
    if result:
        wait, text = result["content"].split(";")
        text = text.strip()
        if text.lower().startswith("url="):
            url=text[4:]
            return url
    return None


def download_ohhle_page(page):
    if page.lower().find('ohhla.com/') == -1:
        url = 'http://ohhla.com/' + page
    else:
        url = page

    r = requests.get(url)
    html_doc = r.text

    return html_doc

def soup_ohhla_page(page):
    html_doc = download_ohhle_page(page)
    soup = BeautifulSoup(html_doc)

    redirect = meta_redirect(soup)
    if redirect:
        return soup_ohhla_page(redirect)

    return soup

def get_ohhla_artist_song_links_dir_listing(artist_page, artist_page_soup):
    result = {}
    
    albums_links = artist_page_soup.select('a')
    albums_links = [{'title': s.string.strip(' /').lower(), 'url': s.attrs['href']} for s in albums_links if s.string.strip() != 'Parent Directory']
    
    for a_link in albums_links:
        result[a_link['title']] = {'title':a_link['title'], 'songs': []}

        # download list of songs in an album
        a_link_full = artist_page + a_link['url']
        album_page_soup = soup_ohhla_page(a_link_full)
        songs_links = album_page_soup.select('a')

        result[a_link['title']]['songs'] = [{'title': s.string.strip(' /').lower(), 'url': a_link_full + s.attrs['href']} for s in songs_links if s.string.strip() != 'Parent Directory']

    return result


def get_ohhla_artist_song_links_formatted(artist_page_soup):
    result = {}

    albums = artist_page_soup.select('a[href^="YFA_"]')
    #print(artist_page_soup)
    #print(albums)
    for a_album in albums:
        #print('-',a_album)
        album_title = a_album.string.lower()

        album_href = a_album.attrs['href']
        sharp_pos = a_album.attrs['href'].find('#')
        if sharp_pos == -1:
            continue
        album_href = album_href[sharp_pos + 1:]
        #print('album href - ',album_href)
        album_a_near_table = artist_page_soup.find('a', {'name': album_href})
        if album_a_near_table is None:
            continue
        #print(album_a_near_table)
        album_table = album_a_near_table.parent.find('table')
        #print(album_table)
        song_links = album_table.select('a[href^="anonymous/"]')
        print(song_links)
        song_data = [{'title': s.string.lower(), 'url': s.attrs['href']} for s in song_links if s.string]


        result[album_title] = {'title': album_title, 'songs': song_data}
    return result
    
    
def get_ohhla_artist_song_links(artist_page):
    soup = soup_ohhla_page(artist_page)

    albums = soup.select('a[href^="YFA_"]')

    if len(albums) == 0: # directody listing
        return get_ohhla_artist_song_links_dir_listing(artist_page, soup)
    else: # formatted page
        return get_ohhla_artist_song_links_formatted(soup)



def get_ohhla_all_pages_artist(page):
    soup = soup_ohhla_page(page)

    links_container = soup.find("pre")

    results = {}
    for child in links_container.findChildren('a'):
        if 'href' in child.attrs:
            artist = child.string.lower()
            url = child.attrs['href']

            results[artist] = { 'artist': artist, 'url': url }

    return results

def get_ohhla_artist_albums(artist, search_letter):
    ohhla_page = get_ohhla_artist_page_name(search_letter)

    if ohhla_page not in ohhla_pages_all_cache:
        ohhla_pages_all_cache[ohhla_page] = get_ohhla_all_pages_artist(ohhla_page)

    if artist not in ohhla_pages_all_cache[ohhla_page]:
        warning('Artist Not Found: ', artist, ohhla_page)
        return None

    if artist not in ohhla_artist_cache:
        album_song_links = get_ohhla_artist_song_links(ohhla_pages_all_cache[ohhla_page][artist]['url'])

        if album_song_links is None:
            warning('Manual Albums: ', artist)
            return None

        ohhla_artist_cache[artist] = album_song_links

    return ohhla_artist_cache[artist]



def get_ohhla_artist_page_name(search_letter):
    ohhla_pages = [
        { 'start': 'a', 'end': 'e', 'page': 'all.html' },
        { 'start': 'f', 'end': 'j', 'page': 'all_two.html' },
        { 'start': 'k', 'end': 'o', 'page': 'all_three.html' },
        { 'start': 'p', 'end': 't', 'page': 'all_four.html' },
        { 'start': 'u', 'end': 'z', 'page': 'all_five.html' },
    ]

    for cat in ohhla_pages:
        if search_letter >= cat['start'] and search_letter <= cat['end']:
            return cat['page']

    return ohhla_pages[0]['page']

def read_data(filename):
    with open(filename, 'r') as csvfile:
        reader = csv.reader(csvfile)

        res = [{'artist': r[0], 'album': r[1] if len(r) > 1 else '<all_albums>', 'search_letter': r[2] if len(r) > 2 else r[0][0] } for r in reader if len(r) != 0]

    return res


def save_song_text(data_dir, artis, album, song, song_text):
    filename = os.path.join(
        data_dir,
        artis.replace(' ', '_').replace('/','_') + '-' + album.replace(' ', '_').replace('/','_') + '-' +  song.replace(' ', '_').replace('/','_') + '.txt'
    )

    with open(filename, 'w') as song_file:
        song_file.write(song_text)


def download_album_songs(artist, album, songs, data_dir):
    for s in songs:
        print('Downloading:', s)

        data = soup_ohhla_page('http://'+s)

        song_tag = data.find('pre')
        if song_tag is None:
            song_tag = data.find('body')

        song_text = song_tag.get_text()
        save_song_text(data_dir, artist, album, s.split('/')[-1].split('.')[0], song_text)



# parse commandline arguments
parser = argparse.ArgumentParser(description='Download hip hip songs from http://www.ohhla.com/')
parser.add_argument("songs", help='file contains links to songs')
parser.add_argument("data_dir", help='output directory to save albums & songs')
args = parser.parse_args()

#artist_album_data = read_data(args.albums)

f = open(args.songs,'r')

songs = {} # format - (artist,album):[songs url list]
import sys
for line in f:
	segments = line.strip().split('/')
	if len(segments)==0: continue
	if len(segments)!=5: 
		sys.stdout.write(line)
		print(len(segments))
		#print(line)
		input()
	if (segments[2],segments[3]) in songs:
		songs[(segments[2],segments[3])].append(line.strip())
	else : songs[(segments[2],segments[3])]=[line.strip()]

for (artist,album) in songs:
	download_album_songs(artist,album,songs[(artist,album)],args.data_dir)

f.close()
"""for a in artist_album_data:
    artist_name = a['artist'].strip().lower()
    need_album_name = a['album'].strip().lower()
    search_letter = a['search_letter'].strip().lower()
    
    print('Process:', artist_name, ' - ', need_album_name)

    artist_albums_data = get_ohhla_artist_albums(artist_name, search_letter)

    if artist_albums_data is None:
        continue

    if need_album_name == '<all_albums>':
        for a in artist_albums_data:
            need_album_name = artist_albums_data[a]['title']
            download_album_songs(artist_name, need_album_name, artist_albums_data[need_album_name]['songs'], args.data_dir)
    else:

        if need_album_name not in artist_albums_data:
            warning('Album Not Found: ', artist_name, ' - ', need_album_name)
            continue

        download_album_songs(artist_name, need_album_name, artist_albums_data[need_album_name]['songs'], args.data_dir)
"""
