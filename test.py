import pyautogui
import keyboard
import time
import os
from ahk import AHK

ahk = AHK()

page_transition_time = 0.86
confidence = 0.9

total_pages = -1
current_page = 0

friend_count = 0

using_zenbook = True
path = './media/zenbook/' if using_zenbook else './media/desktop/'

screen_width, screen_height = pyautogui.size()

def pick_region(region1, region2):
    return region1 if screen_width <= 1920 else region2

def timer():
    start_time = time.time()
    try:
        region = (840, 0, 1087, 1800)
        pyautogui.locateOnScreen('./media/zenbook/candle.png', grayscale=1, region=region, confidence=.6)
        print("Found")
    except:
        pass
    print("--- %s seconds ---" % (time.time() - start_time))

def ss():
    region = (2192, 1701, 60, 60)
    pyautogui.screenshot(region=region).save('region.png')
    try: 
        pyautogui.locateOnScreen('./media/zenbook/q_info.png', grayscale=1, region=region, confidence=.9)
        print("Found")
    except:
        pass

def flare_finder():
    try:
        for pos in pyautogui.locateAllOnScreen('./media/zenbook/flare.png', grayscale=1, confidence=.9):
            pyautogui.moveTo(pos)
            time.sleep(.025)
    except:
        pass

def make_unique_list(list, pixel_distance=3):
    unique_list = []
    for item in list:
        unique = True
        for unique_item in unique_list:
            if abs(unique_item[0] - item[0]) < pixel_distance:
                unique = False
        if unique:
            unique_list.append(item)
    return unique_list

def find_all(image):
    pyautogui.moveTo(500, 0)
    try:
        region = pick_region((190, 160, 1691, 948), (250, 200, 2300, 1360))
        return list(pyautogui.locateAllOnScreen(path+image+'.png', grayscale=1, region=region, confidence=confidence))
    except:
        return []
    
def get_flare_stars():
    positions = make_unique_list(find_all('flare'), pixel_distance=10)
    star_positions = []
    # find groupings of flares that are within 100 px of eachother
    # a group of 3 or more is a star
    # get the center of the star and add that position to a list
    for position in positions:
        x, y = pyautogui.center(position)
        flare_group = []
        for otro_star in positions:
            x2, y2 = pyautogui.center(otro_star)
            hypot = ((x - x2)**2 + (y - y2)**2)**.5
            if hypot < 120:
                flare_group.append(otro_star)
        if len(flare_group) > 1:
            centerpoint = (0, 0)
            for flare_pos in flare_group:
                centerpoint = (centerpoint[0] + flare_pos[0], centerpoint[1] + flare_pos[1])
            centerpoint = (centerpoint[0] / len(flare_group), centerpoint[1] / len(flare_group))
            star_positions.append(centerpoint)
    flare_centers = make_unique_list(star_positions, pixel_distance=20)
    lit_star_locations = make_unique_list(find_all('lit_friend'), pixel_distance=10)
    final_star_positions = []
    for star in flare_centers:
        # find closest lit star to this star
        closest = 200
        closest_star = None
        for lit_star in lit_star_locations:
            distance = ((star[0] - lit_star[0])**2 + (star[1] - lit_star[1])**2)**.5
            if distance < closest:
                closest = distance
                closest_star = lit_star
        final_star_positions.append(closest_star)
    return final_star_positions

def find_flare_stars():
    # go inside path./lit_friends/* and go through all pictures in that folder
    # and match with one screenshot of the screen
    # return a list of unique positions (50px) of all results
    results = []
    for picture in os.listdir(path+'lit_friends'):
        # temp screenshot 
        pyautogui.screenshot('temp.png')
        try:
            region = pick_region((190, 160, 1691, 948), (250, 200, 2300, 1360))
            positions = list(pyautogui.locateAll(needleImage=(path+'lit_friends/'+picture), haystackImage='./temp.png', grayscale=1, region=region, confidence=.9))
            for position in positions:
                x, y = pyautogui.center(position)
                results.append((x, y))
        except:
            pass
        # delete temp screenshot
        os.remove('temp.png')
    
    return make_unique_list(results, pixel_distance=50)

def confidences():
    for i in range(4, 10):
        conf = i/100 + .9
        for picture in os.listdir(path+'lit_friends'):
            # temp screenshot 
            pyautogui.screenshot('temp.png')
            length = []
            region = pick_region((190, 160, 1691, 948), (250, 200, 2300, 1360))
            positions = list(pyautogui.locateAll(needleImage=(path+'lit_friends/'+picture), haystackImage='./temp.png', grayscale=1, region=region, confidence=conf))
            for position in positions:
                x, y = pyautogui.center(position)
                length.append((x, y))
            print(str(len(length)) + ' found with confidence ' + str(conf))

if __name__ == '__main__':
    time.sleep(.5)
    arr = get_flare_stars()
    for pos in arr:
        pyautogui.moveTo(pos)
        time.sleep(.1)
    print(len(arr))
    # confidences()