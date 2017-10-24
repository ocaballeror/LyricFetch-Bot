#/usr/bin/env python3

# Find lyrics for all the .mp3 files in the current directory
# and write them as metadata for the files
#
# LIST OF LYRICS SITES (X marks implemented)
# lyrics.wikia.com    X
# metrolyrics.com     X
# azlyrics.com        X
# lyrics.com          X
# darklyrics.com      X
# genius.com          X
# vagalume.com.br     X
# musixmatch.com      X
# songlyrics.com
# lyricsmode.com      X
# metal-archives.com  X
# letras.mus.br       X
# musica.com          X

# TODO 
# Darklyrics was left out of the sources list because it needs the album name
# to work, which is a weird thing to ask to a user. Figure out how to guess the
# album name just based on the title and artist and include Darklyrics again.

import sys
import time
import re
import logging
import ssl
import urllib.request as request

from urllib.error import *
from http.client import HTTPException
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Send verbose logs to a log file
debuglogger = logging.FileHandler('debuglog', 'w')
debuglogger.setLevel(logging.DEBUG)
logger.addHandler(debuglogger)

# Send error logs to an errlog file
errlogger = logging.FileHandler('errlog', 'w')
errlogger.setLevel(logging.WARNING)
logger.addHandler(errlogger)

# Discard eyed3 messages unless they're important
logging.getLogger("eyed3.mp3.headers").setLevel(logging.CRITICAL)

def bs(url, safe=":/"):
    '''Requests the specified url and returns a BeautifulSoup object with its
    contents'''
    url = request.quote(url,safe=safe)
    logger.debug('URL: %s', url)
    req = request.Request(url, headers={"User-Agent": "foobar"})
    try:
        response = request.urlopen(req)
    except (ssl.SSLError, URLError) as e:
        # Some websites (like metal-archives) use older TLS versions and can
        # make the ssl module trow a VERSION_TOO_LOW error. Here we try to use
        # the older TLSv1 to see if we can fix that
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        response = request.urlopen(req, context=context)

    return BeautifulSoup(response.read(), 'html.parser')

# Contains the characters usually removed or replaced in URLS
urlescape = ".¿?%_@,;&\\/()'\"-!¡"
urlescapeS = ' '+urlescape
def normalize(string, chars_to_remove=None, replacement=''):
    """Remove accented characters and such.
    The argument charsToRemove is a dictionary that maps a string of chars
    to a single character. Every ocurrence of every character in the first
    string will be replaced by that second charcter passed as value. If only
    one mapping is desired, charsToRemove may be a single string, but a third
    parameter, replacement, must be provided to complete the translation."""

    ret = string.translate(str.maketrans({
        'á': 'a',
        'é': 'e',
        'í': 'i',
        'ó': 'o',
        'ö': 'o',
        'ú': 'u',
        'ü': 'u',
        'ñ': 'n'
    }))

    if isinstance(chars_to_remove, dict):
        for chars,replace in chars_to_remove.items():
            reg = "["+re.escape(chars)+"]"
            ret = re.sub(reg, replace, ret)

    elif isinstance(chars_to_remove, str):
        reg = '['+re.escape(chars_to_remove)+']'
        ret = re.sub(reg, replacement, ret)

    return ret

def metrolyrics(artist, title):
    '''Returns the lyrics found in metrolyrics for the specified mp3 file or an
    empty string if not found'''
    translate = {urlescape: "", " ":"-"}
    title = title.lower()
    title = normalize(title, translate)
    title = re.sub(r'\-{2,}', '-', title)
    artist = artist.lower()
    artist = normalize(artist, translate)
    artist = re.sub(r'\-{2,}', '-', artist)

    url = "http://www.metrolyrics.com/{}-lyrics-{}.html".format(title, artist)
    soup = bs(url)
    body = soup.find(id="lyrics-body-text")
    if body is None:
        return ""

    text = ""
    verses = body.find_all('p')
    for verse in verses:
        text += verse.get_text().strip()
        text += '\n\n'

    return text.strip()

def darklyrics(artist, title):
    '''Returns the lyrics found in darklyrics for the specified mp3 file or an
    empty string if not found'''
    artist = artist.lower()
    artist = normalize(artist, urlescapeS, '')
    album = mp3file.tag.album.lower()
    album = normalize(album, urlescapeS, '')
    title = title

    url = "http://www.darklyrics.com/lyrics/{}/{}.html".format(artist, album)
    soup = bs(url)
    text = ""
    for header in soup.find_all('h3'):
        song = str(header.get_text())
        next_sibling = header.next_sibling
        if song.lower().find(title.lower()) != -1:
            while next_sibling is not None and (next_sibling.name is None\
                or next_sibling.name != 'h3'):
                if next_sibling.name is None:
                    text += str(next_sibling)
                next_sibling = next_sibling.next_sibling

    return text.strip()

def azlyrics(artist, title):
    '''Returns the lyrics found in azlyrics for the specified mp3 file or an
    empty string if not found'''
    artist = artist.lower()
    if artist[0:2] == "a ":
        artist = artist[2:]
    artist = normalize(artist, urlescapeS, "")
    title = title.lower()
    title = normalize(title, urlescapeS, "")

    url = "https://www.azlyrics.com/lyrics/{}/{}.html".format(artist, title)
    soup = bs(url)
    body = soup.find_all('div', class_="")[-1]
    return body.get_text().strip()

def genius(artist, title):
    '''Returns the lyrics found in genius.com for the specified mp3 file or an
    empty string if not found'''
    translate = {
        '@': 'at',
        '&': 'and',
        urlescape: '',
        ' ': '-'
    }
    artist = artist.capitalize()
    artist = normalize(artist, translate)
    title = title.capitalize()
    title = normalize(title, translate)

    url = "https://www.genius.com/{}-{}-lyrics".format(artist, title)
    soup = bs(url)
    for content in soup.find_all('p'):
        if content:
            text = content.get_text().strip()
            if text:
                return text

    return ''

def metalarchives(artist, title):
    '''Returns the lyrics found in MetalArchives for the specified mp3 file or an
    empty string if not found'''
    artist = artist.capitalize()
    artist = normalize(artist, ' ', '_')
    title = title.capitalize()
    title = normalize(title, ' ', '_')

    url = "https://www.metal-archives.com/search/ajax-advanced/searching/songs/"
    url += f"?songTitle={title}&bandName={artist}&exactBandMatch=1"
    soup = bs(url, safe=':/?=&')

    song_id = ''
    song_id_re = re.compile(r'lyricsLink_([0-9]*)')
    for link in soup.find_all('a'):
        song_id = re.search(song_id_re, str(link))
        if song_id:
            song_id = song_id.group(1)
            break

    if not song_id:
        return ""

    url="https://www.metal-archives.com/release/ajax-view-lyrics/id/{}".format(song_id)
    soup = bs(url)
    text = soup.get_text()
    if re.search('lyrics not available', text):
        return ""
    else:
        return text.strip()

def lyricswikia(artist, title):
    '''Returns the lyrics found in lyrics.wikia.com for the specified mp3 file or an
    empty string if not found'''
    artist = artist.title()
    artist = normalize(artist, ' ', '_')
    title = title
    title = normalize(title, ' ', '_')

    url = "https://lyrics.wikia.com/wiki/{}:{}".format(artist, title)
    soup = bs(url)
    text = ""
    content = soup.find('div', class_='lyricbox')
    if not content:
        return ""

    for unformat in content.findChildren(['i','b']):
        unformat.unwrap()
    for remove in content.findChildren('div'):
        remove.decompose()

    nlcount = 0
    for line in content.children:
        if line is None or line=='<br/>' or line=='\n':
            if nlcount==2:
                text += "\n\n"
                nlcount = 0
            else:
                nlcount += 1
        else:
            nlcount = 0
            text += str(line).replace('<br/>', '\n')
    return text.strip()

def musixmatch(artist, title):
    '''Returns the lyrics found in musixmatch for the specified mp3 file or an
    empty string if not found'''
    escape = re.sub("'-¡¿", '', urlescape)
    translate = {
        escape: "",
        " ": "-"
    }
    artist = artist.title()
    artist = re.sub(r"( '|' )", "", artist)
    artist = re.sub(r"'", "-", artist)
    title = title
    title = re.sub(r"( '|' )", "", title)
    title = re.sub(r"'", "-", title)

    artist = normalize(artist, translate)
    artist = re.sub(r'\-{2,}', '-', artist)
    title = normalize(title, translate)
    title = re.sub(r'\-{2,}', '-', title)

    url = "https://www.musixmatch.com/lyrics/{}/{}".format(artist, title)
    soup = bs(url)
    text = ""
    contents = soup.find_all('p', class_='mxm-lyrics__content ')
    for p in contents:
        text += p.get_text().strip()
        if p != contents[-1]:
            text += '\n\n'

    return text.strip()

# Songlyrics is basically a mirror for musixmatch, so it helps us getting
# around musixmatch's bot detection (they block IPs pretty easily)
def songlyrics(artist, title):
    '''Returns the lyrics found in songlyrics.com for the specified mp3 file or
    an empty string if not found'''
    translate = {
        urlescape: "",
        " ": "-"
    }
    artist = artist.lower()
    artist = normalize(artist, translate)
    title = title.lower()
    title = normalize(title, translate)

    artist = re.sub(r'\-{2,}', '-', artist)
    title = re.sub(r'\-{2,}', '-', title)

    url = "http://www.songlyrics.com/{}/{}-lyrics".format(artist, title)
    soup = bs(url)
    text = soup.find(id='songLyricsDiv')
    if not text:
        return ""

    return text.getText().strip()

def lyricscom(artist, title):
    '''Returns the lyrics found in lyrics.com for the specified mp3 file or an
    empty string if not found'''
    artist = artist.lower()
    artist = normalize(artist, " ", "+")
    title = title

    url = "https://www.lyrics.com/artist/{}".format(artist)
    soup = bs(url)
    location=""
    for a in soup.select('tr a'):
        if a.string.lower() == title.lower():
            location = a['href']
            break
    if location == "":
        return ""

    url = "https://www.lyrics.com"+location
    soup = bs(url)
    body = soup.find(id="lyric-body-text")
    if not body:
        return ""

    return body.get_text().strip()

def vagalume(artist, title):
    '''Returns the lyrics found in vagalume.com.br for the specified mp3 file or an
    empty string if not found'''
    translate = {
        '@': 'a',
        urlescape: '',
        ' ': '-'
    }
    artist = artist.lower()
    artist = normalize(artist, translate)
    artist = re.sub(r'\-{2,}', '-', artist)
    title = title.lower()
    title = normalize(title, translate)
    title = re.sub(r'\-{2,}', '-', title)

    url = "https://www.vagalume.com.br/{}/{}.html".format(artist, title)
    soup = bs(url)
    body = soup.select('div[itemprop="description"]')
    if body == []:
        return ""

    content = body[0]
    for br in content.find_all('br'):
        br.replace_with('\n')

    return content.get_text().strip()

def lyricsmode(artist, title):
    '''Returns the lyrics found in lyricsmode.com for the specified mp3 file or an
    empty string if not found'''
    translate = {
        urlescape: "",
        " ": "_"
    }
    artist = artist.lower()
    artist = normalize(artist, translate)
    title = title.lower()
    title = normalize(title, translate)

    artist = re.sub(r'\_{2,}', '_', artist)
    title = re.sub(r'\_{2,}', '_', title)

    if artist[0:4].lower() == "the ":
        artist = artist[4:]

    if artist[0:2].lower() == 'a ':
        prefix = artist[2]
    else:
        prefix = artist[0]

    url = "http://www.lyricsmode.com/lyrics/{}/{}/{}.html".format(prefix,
            artist, title)
    soup = bs(url)
    content = soup.find(id="lyrics_text")

    return content.get_text().strip()

def letras(artist, title):
    '''Returns the lyrics found in letras.com for the specified mp3 file or an
    empty string if not found'''
    translate = {
        "&": "a",
        urlescape: "",
        " ": "-"
    }
    artist = artist.lower()
    artist = normalize(artist, translate)
    title = title.lower()
    title = normalize(title, translate)

    url = "https://www.letras.com/{}/{}/".format(artist, title)
    soup = bs(url)
    content = soup.find('article')
    if not content:
        return ""

    text = ""
    for br in content.find_all('br'):
        br.replace_with('\n')

    for p in content.find_all('p'):
        text += p.get_text()

    return text.strip()

def musica(artist, title):
    '''Returns the lyrics found in musica.com for the specified mp3 file or an
    empty string if not found'''
    safe = "?=:/"
    artist = artist.title()
    artist = normalize(artist)
    title = title.title()
    title = normalize(title.lower())

    url = "https://www.musica.com/letras.asp?t2="+artist
    soup = bs(url, safe=safe)
    first_res = soup.find(href=re.compile(r'https://www.musica.com/letras.asp\?letras=.*'))
    if first_res is None:
        return ""

    url = first_res['href']
    soup = bs(url, safe = safe)
    for a in soup.find_all('a'):
        if re.search(re.escape(title)+"$", a.text, re.IGNORECASE):
            first_res = a
            break
    else:
        return ""

    url = "https://www.musica.com/"+first_res['href']
    soup = bs(url, safe=safe)
    content = soup.p
    if not content:
        return ""

    for rem in content.find_all('font'):
        rem.unwrap()
    for googlead in content.find_all(['script', 'ins']):
        googlead.decompose()

    text = str(content)
    text = re.sub(r'<.?p>','',text)
    text = re.sub(r'<.?br.?>','\n', text)

    return text.strip()


sources = [
    azlyrics,
    metrolyrics,
    lyricswikia,
    metalarchives,
    genius,
    musixmatch,
    songlyrics,
    vagalume,
    letras,
    lyricsmode,
    lyricscom,
    musica
]

def id_source(source, full=False):
    '''Returns the name of a website-scrapping function'''
    if source == azlyrics:
        name = "AZLyrics.com" if full else 'AZL'
    elif source == metrolyrics:
        name = "MetroLyrics.com" if full else 'MET'
    elif source == lyricswikia:
        name = "lyrics.wikia.com" if full else 'WIK'
    elif source == darklyrics:
        name = "DarkLyrics.com" if full else 'DAR'
    elif source == metalarchives:
        name = "Metal-archives.com" if full else 'ARC'
    elif source == genius:
        name = "Genius.com" if full else 'GEN'
    elif source == musixmatch:
        name = "Musixmatch.com" if full else 'XMA'
    elif source == songlyrics:
        name = "SongLyrics.com" if full else 'SON'
    elif source == vagalume:
        name = "Vagalume.com.br" if full else 'VAG'
    elif source == letras:
        name = "Letras.com" if full else 'LET'
    elif source == lyricsmode:
        name = "Lyricsmode.com" if full else 'LYM'
    elif source == lyricscom:
        name = "Lyrics.com" if full else 'LYC'
    elif source == musica:
        name = "Musica.com" if full else'MUS'
    else:
        name = ''

    return name

class Result:
    """Contains the results generated from run_mp, so they can be returned as a
    single variable"""
    def __init__(self, source=None, artist="", title="", lyrics="", runtimes={}):
        # The source where the lyrics were found (or None if they weren't)
        self.source = source

        # The song info
        self.artist = artist
        self.title = title
        self.lyrics = lyrics

        # A dictionary that maps every source to the time taken to scrape
        # the website. Keys corresponding to unused sources will be missing
        self.runtimes = runtimes

def run(artist, title):
    """Searches for lyrics of a single song and returns an mp_res object with
    the various stats collected in the process. It is intended to be an
    auxiliary function to run, which will invoke it as a parallel process"""
    logger.info(f'{artist} - {title}')

    lyrics = ""
    start = 0
    end = 0
    runtimes = {}
    for source in sources:
        try:
            start = time.time()
            lyrics = source(artist, title)
            end = time.time()
            runtimes[source] = end-start

            if lyrics != '':
                logger.info(f'++ {source.__name__}: Found lyrics for {artist} - {title}\n')

                return Result(source, artist, title, lyrics, runtimes)
            else:
                logger.info(f'-- {source.__name__}: Could not find lyrics for {artist} - {title}\n')

        except (HTTPError, HTTPException, URLError, ConnectionError) as e:
            # if not hasattr(e, 'code') or e.code != 404:
            #     logger.exception(f'== {source.__name__}: {e}\n')
            logger.info(f'-- {source.__name__}: Could not find lyrics for {artist} - {title}\n')

        finally:
            end = time.time()
            runtimes[source] = end-start

    return Result(artist=artist, title=title, runtimes=runtimes)

def parseargs(args):
    if isinstance(args, str):
        recv = [ t.strip() for t in args.split("-") ]
        if len(recv) != 2:
            sys.stderr.write('Wrong format!\n')
            return None

        artist = recv[0]
        title = recv[1]
    elif isinstance(args, list):
        try:
            split = args.index('-')
        except ValueError:
            sys.stderr.write('Wrong format!\n')
            return None

        artist = ''.join(args[0:split])
        title = ''.join(args[split+1:])

    else:
        sys.stderr.write('WTF are these arguments\n')
        return None

    return artist, title

def find_lyrics(args):
    res = parseargs(args)
    if res is None:
        return None

    artist, title = res
    if artist is None or title is None:
        return None

    return run(artist, title)

# Yes I know this is not the most pythonic way to do things, but it helps me
# organize my code.
def main():
    try:
        if len(sys.argv) > 1:
            ret = parseargs(sys.argv[1:])
        else:
            read = input('Input artist - title: ')
            ret = parseargs(read)

        if ret is None:
            return 1
        else:
            artist,title = ret
            if artist is None or title is None:
                return 1

        res = run(artist, title)
        if res.source is None:
            print(f'Lyrics for {artist} - {title} not found')
        else:
            print(f'FROM: {id_source(res.source, True)}\n\n{res.lyrics}')

    except KeyboardInterrupt:
        print ("Interrupted")

    return 0

if __name__=='__main__':
    exit(main())
