#!/usr/bin/env python3

import argparse
from lxml import html
from urllib.request import urlopen
from datetime import datetime, timedelta
import os
import sys
from enum import Enum

class MeldMethods(Enum):
    DIRECT = 1
    SIMPLE_TRIM = 2
    #DELTA_CORRELATION = 3
    #SPEED_CHANGE = 4
    NONE_IDENTIFIED = 5

meld_methods_short_desc = { MeldMethods.DIRECT : 'Direct Correlation'
                         , MeldMethods.SIMPLE_TRIM : 'Single Chapter Trim'
                         #, MeldMethods.DELTA_CORRELATION : 'Direct Time Similarity'
                         #, MeldMethods.SPEED_CHANGE : 'Time Similarity After Speed Change'
                         , MeldMethods.NONE_IDENTIFIED : 'None Identified'}

def fill_line(capstr='',char='#',centertext=''):
    if len(char) == 0:
        char = '#'
    rows, columns = os.popen('stty size', 'r').read().split()
    line = centertext.center(int(columns)-(2*len(capstr)),char)
    print(capstr+line+capstr)
    return

def get_results(search):
    results = []
    encode = search.replace(' ','+')
    with urlopen("https://www.barnesandnoble.com/s/"
                                  + "{}/_/N-8qh".format(encode)) as page:
        tree = html.fromstring(page.read())
    #Have we been redirected to a product page?
    pres_elem = tree.xpath('//li[@role="presentation"]')
    if len(pres_elem)>0:
        #We've been redirected
        title = tree.xpath('//h1[@itemprop="name"]/text()')
        entry = {'title':title[0]}
        director_elements = tree.xpath('//div[@class="lists authors lists--unstyled lists--horizontal "]/span/a/text()')
        entry['directors'] = director_elements
        url = tree.xpath('//meta[@property="og:url"]/@content')
        entry['url'] = url[0].replace('http://www.barnesandnoble.com','')
        results += [entry]
    else:
        #We've got a results page
        films = tree.xpath('//div[@class="product-shelf-tile  columns-5"]')
        for film in films:
            title = film.find_class("product-shelf-title product-info-title pt-xs")[0].text_content()[1:]
            entry = {'title':title}
            director_elements = film.find_class("product-shelf-author pt-0")
            if len(director_elements) != 0:
                directors_a = director_elements[0].xpath('a')
                directors = []
                for director_a in directors_a:
                    directors += [director_a.text_content()]
                entry['directors'] = directors
            else:
                entry['directors']  = []
            url = film.find_class("pImageLink")[0].xpath("@href")
            entry['url'] = url[0]
            results += [entry]
            #print(film_title,film_director)
    return results

def get_chapters(url):
    with urlopen("http://www.barnesandnoble.com"+url+"#SceneIndex") as page:
        tree = html.fromstring(page.read())
    chapters = []
    times = []
    sames = []
    scenes = tree.xpath('//div[@id="SceneIndex"]/div[@id="productInfo-sceneindex"]/div[@class="text--center text--medium"]/text()')
    if len(scenes) > 0:
        scenes = scenes[1:]
        count = 0
        for scene in scenes:
            #print(scene)
            if scene.startswith("Side"):
                break
            if scene.startswith("Disc"):
                break
            if scene.startswith("0."):
                continue
            if scene.find("Chapter Selection") > 0:
                continue
            if scene.find('[') > 0:
                count += 1
                timestamp = scene[scene.find('[')+1:scene.find(']')]
                times = []
                while timestamp.find(':') >= 0:
                    times += [timestamp[:timestamp.find(':')]]
                    timestamp = timestamp[timestamp.find(':')+1:]
                hours=0
                minutes=0
                seconds=0
                times = times[::-1]
                acount = 0
                for time in times:
                    if acount == 0:
                        seconds = int('0'+time)
                    elif acount == 1:
                        minutes = int('0'+time)
                    else:
                        hours = int('0'+time)
                    acount += 1
                #str_minutes = timestamp[:timestamp.find(':')]
                #if len(str_minutes) == 0:
                #    minutes = 0
                #else:
                #    minutes = int(str_minutes)
                #print(scene)
                #str_seconds = timestamp[timestamp.find(':')+1:]
                #if len(str_seconds) == 0:
                #    seconds = 0
                #else:
                #    seconds = int(str_seconds)

                if count == 1:
                    tot_time = timedelta(hours=hours,minutes=minutes,seconds=seconds)
                else:
                    tot_time += timedelta(hours=hours,minutes=minutes,seconds=seconds)

                times += [tot_time]
            fixed_scene = scene[:(scene.find('[')-1)].strip()
            chapters += [fixed_scene]
            sames += [fixed_scene[3:-2]]
    #print(sames)
    if len(set(sames[:9])) > 1:
        descriptive = True
    else:
        descriptive = False
    return chapters,times,descriptive

def open_txt_chapters(filename):
    with open(filename, 'r') as myfile:
        lines = myfile.readlines()
    count = -1
    times = []
    for line in lines:
        count += 1
        if count % 2 == 0:
            #"CHAPTERXX="" Line? Will confirm validity of file.
            if not ((line.startswith("CHAPTER")) and (line.find("=") == 9)):
               return []
            timestr = line[line.find("=")+1:-1]
            #print(timestr)
            t = datetime.strptime(timestr,"%H:%M:%S.%f")
            times += [timedelta(hours=t.hour, minutes=t.minute
                                , seconds=t.second
                                , microseconds=t.microsecond)]
    return times

def best_method(realtimes,times):
    #Equal number of chapters online and locally?
    if (len(realtimes) == len(times)):
        return MeldMethods.DIRECT
    #Nearly equal number of chapters online and locally?
    if abs(len(realtimes) - len(times)) == 1:
        return MeldMethods.SIMPLE_TRIM
    #We can't see a good method.
    return MeldMethods.NONE_IDENTIFIED

def direct_meld(realtimes,chapters):
    return realtimes, chapters

def simple_trim_meld(realtimes,chapters):
    #Are there less real chapters than online?
    if len(realtimes) < len(chapters):
        return realtimes[:-1], chapters
    #So there are more online chapters than real...
    else:
        return realtimes, chapters[:-1]

def construct_chapters(realtimes,chapters):
    final = ''
    for i in range(len(realtimes)):
        time = datetime(year=1984, month=6, day=24) +realtimes[i]
        strtime = time.strftime("%H:%M:%S.%f")[:-3]
        name = chapters[i]
        final += "CHAPTER{:02d}={}\n".format(count,strtime)
        final += "CHAPTER{:02d}NAME={}\n".format(count,name)
    return final

def write_chapters(chapterstr,filename):
    new_chaps = open(filename, 'w+')
    new_chaps.write(chapterstr)
    new_chaps.close()
    return

#Called if this script is executed from the terminal
if __name__ == "__main__":
    #Retrieve the arguments from the terminal
    parser = argparse.ArgumentParser(description='Fetch chapters for a film name')
    parser.add_argument('search', metavar='N', type=str, nargs='+',
                        help='The search string')
    requiredNamed = parser.add_argument_group('required arguments')
    requiredNamed.add_argument('-i','--input',action='store',nargs=1,required=True,
                        help='The .txt chapters file in OGM format.')
    parser.add_argument('-o','--output',action='store',nargs=1,required=False,
                        help='The name and location to save the chapters.'
                             +' Default is in the chapter directory with _NEW'
                             +' appended.', default='*DEFAULT*')
    args = parser.parse_args()
    search = ' '.join(args.search)
    filename = args.input[0]
    realtimes = open_txt_chapters(filename)
    if len(realtimes) == 0:
        print("Invalid or empty chapter file")
    else:
        fill_line(char='%')
        fill_line(char=' ',capstr='%'
                  ,centertext='No. of chapters in chapter file: {}'.format(len(realtimes)))
        fill_line(char='%')
        results = get_results(search)
        count = -1
        valid_results = []
        fill_line()
        fill_line(char=' ',capstr='#',centertext='Barnes&Noble Results')
        fill_line()
        for result in results:
            chapters,times,descriptive = get_chapters(result['url'])
            if len(chapters) > 0:
                count += 1
                result['chapters'] = chapters
                result['times'] = times
                result['descriptive'] = descriptive
                result['method'] = best_method(realtimes,times)
                valid_results += [result]
                outstr = "{}) {}".format(count,result['title'])
                if len(result['directors']) > 0:
                    outstr += " <Directed by " + ','.join(result['directors']) + ">"
                outstr += " ({} Chapters)".format(len(result['chapters']))
                if descriptive:
                    outstr += " [Descriptive]"
                else:
                    outstr += " [Non-Descriptive]"
                outstr += ' {'+"{}".format(meld_methods_short_desc[result['method']])+'}'
                print(outstr)
        fill_line()
        if len(valid_results) > 0:
            workable_choice = False
            #Get a valid option from the user
            while not workable_choice:
                desc_choice = False
                while not desc_choice:
                    choice = 'invalid'
                    while choice not in list(str(i) for i in range(-1,count+1)):
                        choice = input("Select a descriptive, workable result index ([0-{}] or -1 for none): ".format(count))
                    if int(choice) < 0:
                        sys.exit()
                    if valid_results[int(choice)]['descriptive']:
                        desc_choice = True
                if valid_results[int(choice)]['method'] != MeldMethods.NONE_IDENTIFIED:
                    workable_choice = True
            #Process the option
            fill_line()
            if valid_results[int(choice)]['method'] == MeldMethods.DIRECT:
                realtimes, chapters = direct_meld(realtimes,chapters)
            elif valid_results[int(choice)]['method'] == MeldMethods.SIMPLE_TRIM:
                realtimes, chapters = simple_trim_meld(realtimes,chapters)
            final = construct_chapters(realtimes,valid_results[int(choice)]['chapters'])
            if type(args.output) == type([]):
                outfilename = args.output[0]
            else:
                outfilename = os.path.join(os.path.dirname(filename),os.path.splitext(filename)[0]+'_NEW.txt')
            write_chapters(final,outfilename)
            fill_line(char='=')
            print('New chapters saved to '+outfilename)
