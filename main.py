from pyautogui import *
import pyautogui
import keyboard
from ahk import AHK
import time

ahk = AHK()

page_transition_time = 0.86
confidence = 0.9

total_pages = -1
current_page = 0

friend_count = 0
light_collected = 0

screen_width, screen_height = pyautogui.size()

using_zenbook = screen_width > 1920
path = './media/zenbook/' if using_zenbook else './media/desktop/'

def pick_region(region1, region2):
    return region1 if not using_zenbook else region2

def press_key(key):
    try:
        region = pick_region((1765, 1026, 120, 50), (2610, 1700, 200, 100))
        pyautogui.locateOnScreen(path+'esc.png', grayscale=1, region=region, confidence=.7)
        ahk.key_down(key)
        time.sleep(.1)
        ahk.key_up(key)
        return 1
    except:
        print("Esc not found")
        return 0

def attempt_reentry():
    try:
        pyautogui.locateOnScreen(path+'const.png', grayscale=1, confidence=0.6)
        key = 'f'
        ahk.key_down(key)
        time.sleep(.1)
        ahk.key_up(key)
        return 1
    except:
        return 0

def enter_ui():
    if attempt_reentry():
        return
    
    for _ in range(7):
        pyautogui.scroll(25)
        pyautogui.moveTo(pyautogui.size()[0]/2, pyautogui.size()[1])
    
    attempts = 50
    
    while attempts > 0:
        if (attempt_reentry()):
            break
        attempts -= 1
        pyautogui.moveTo(1591, 932)
        pass
    time.sleep(3)


def index_to_start():
    try:
        pyautogui.locateOnScreen(path+'add_friends.png', grayscale=1, confidence=confidence)
        return
    except:
        key = 'z'
        ahk.key_down(key)
        time.sleep(.1)
        ahk.key_up(key)
        index_to_start()

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

# run AFTER we index or else everything explodes
def get_total_pages():
    left, top, width, height = pyautogui.locateOnScreen(path+'add_friends.png', grayscale=1, confidence=confidence)
    screen_width, screen_height = pyautogui.size()
    region=(left, top+height, int(screen_width*0.12), screen_height-(top+height))
    try:
        positions = pyautogui.locateAllOnScreen(path+'page_bubble_online.png', grayscale=0, region=region, confidence=confidence)
        pages_online = positions
    except:
        pages_online = 0
        print("No online")
    try:
        positions = pyautogui.locateAllOnScreen(path+'page_bubble.png', grayscale=0, region=region, confidence=confidence)
        pages_offline = positions
    except:
        pages_offline = 0
        print("No offline")
    return len(make_unique_list(list(pages_online) + list(pages_offline)))

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
        closest = 9999
        closest_star = None
        for lit_star in lit_star_locations:
            distance = ((star[0] - lit_star[0])**2 + (star[1] - lit_star[1])**2)**.5
            if distance < closest:
                closest = distance
                closest_star = lit_star
        final_star_positions.append(closest_star)
    return final_star_positions
    
def wait_for_candle(duration):
    start_time = time.time()
    while time.time() - start_time < duration:
        # Considering the search takes .24 seconds, 
        # if we have less than .24 seconds left, 
        # we should just wait it out
        if duration-(time.time() - start_time) < 0.24:
            time.sleep(duration-(time.time() - start_time))
        try:
            region = pick_region((0,0,0,0), (840, 0, 1087, 1800))
            pyautogui.locateOnScreen(path+'candle.png', grayscale=1, region=region, confidence=.6)
            time.sleep(.1)
            return 1
        except:
            pass
    return 0

def light_friend(x, y):
    pyautogui.click(x, y)
    
    time.sleep(.3)

    skip = 0
    try:
        region = pick_region((1540, 1025, 30, 30), (2192, 1701, 60, 60))
        q_position = pyautogui.locateOnScreen(path+'q_info.png', grayscale=1, region=region, confidence=confidence)
        # we still arent in the UI-- we need to click again
        pyautogui.click(x, y)
        pyautogui.moveTo(q_position)
        time.sleep(.2)
    except:
        # We couldn't find the info page, so let's make sure we didn't misclick
        try:
            skip = pyautogui.locateOnScreen(path+'candle.png', grayscale=1, confidence=0.6)
        except:
            try:
                pyautogui.locateOnScreen(path+'esc.png', grayscale=1, confidence=0.6)
            except:
                enter_ui()
                return
    if not skip:
        wait_for_candle(.9)
    
    press_key('f')
    time.sleep(.2)
    press_key('esc')
    time.sleep(.3)
    global friend_count
    friend_count += 1

def loop():
    press_key('c')
    global current_page, light_collected
    while current_page <= total_pages:
        # this loop helps double check missed friends
        while True:
            friends = make_unique_list(find_all('unlit_friend'), pixel_distance=10)
            if len(friends) == 0:
                for star in get_flare_stars():
                    pyautogui.click(star)
                    light_collected += 1
                    time.sleep(.1)
                break
            for friend in friends:
                x, y = pyautogui.center(friend)
                light_friend(x, y)
        press_key('c')
        time.sleep(page_transition_time)
        pyautogui.moveTo(501, 0)
        current_page += 1

if __name__ == "__main__":
    print("Starting!!")
    start_time = time.time()
    time.sleep(1)
    try:
        pyautogui.locateOnScreen(path+'esc.png', grayscale=1, confidence=0.6)
    except:
        enter_ui()
    index_to_start()
    total_pages = get_total_pages()
    print(f"Total pages: {total_pages}")
    loop()
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Lit {friend_count} friends, and collected {light_collected} light in {int(elapsed_time)} seconds")