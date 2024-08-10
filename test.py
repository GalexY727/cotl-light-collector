import pyautogui
import keyboard
import time
import os
from ahk import AHK
import json

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
    with open('config.json') as f:
        config = json.load(f)
    
    positions = make_unique_list(find_all(config['flare_image']), pixel_distance=config['pixel_distance'])
    star_positions = []
    
    for position in positions:
        x, y = pyautogui.center(position)
        flare_group = []
        
        for otro_star in positions:
            x2, y2 = pyautogui.center(otro_star)
            hypot = ((x - x2)**2 + (y - y2)**2)**.5
            
            if hypot < config['flare_group_distance']:
                flare_group.append(otro_star)
        
        if len(flare_group) > config['flare_group_size']:
            centerpoint = (0, 0)
            
            for flare_pos in flare_group:
                centerpoint = (centerpoint[0] + flare_pos[0], centerpoint[1] + flare_pos[1])
            
            centerpoint = (centerpoint[0] / len(flare_group), centerpoint[1] / len(flare_group))
            star_positions.append(centerpoint)
    
    flare_centers = make_unique_list(star_positions, pixel_distance=config['flare_center_distance'])
    lit_star_locations = make_unique_list(find_all(config['lit_friend_image']), pixel_distance=config['lit_star_distance'])
    final_star_positions = []
    
    for star in flare_centers:
        closest = config['closest_distance']
        closest_star = None
        
        for lit_star in lit_star_locations:
            distance = ((star[0] - lit_star[0])**2 + (star[1] - lit_star[1])**2)**.5
            
            if distance < closest:
                closest = distance
                closest_star = lit_star
        
        final_star_positions.append(closest_star)
    
    return final_star_positions

if __name__ == '__main__':
    time.sleep(.5)
    arr = get_flare_stars()
    for pos in arr:
        pyautogui.moveTo(pos)
        time.sleep(.1)
    print(len(arr))
    # confidences()