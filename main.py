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

def press_key(key):
    try:
        pyautogui.locateOnScreen('./media/esc.png', grayscale=1, region=(1765, 1026, 120, 50), confidence=.7)
        ahk.key_down(key)
        time.sleep(.1)
        ahk.key_up(key)
        return 1
    except:
        print("Esc not found")
        return 0

def attempt_reentry():
    try:
        pyautogui.locateOnScreen('./media/const.png', grayscale=1, confidence=0.6)
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
        pyautogui.scroll(100)
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
        pyautogui.locateOnScreen('./media/add_friends.png', grayscale=1, confidence=confidence)
        return
    except:
        ahk.key_press('z')
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
    left, top, width, height = pyautogui.locateOnScreen('./media/add_friends.png', grayscale=1, confidence=confidence)
    screen_width, screen_height = pyautogui.size()
    try:
        positions = pyautogui.locateAllOnScreen('./media/page_bubble_online.png', grayscale=0, region=(left, top+height, 220, screen_height-(top+height)), confidence=confidence)
        pages_online = positions
    except:
        pages_online = 0
        print("No online")
    try:
        positions = pyautogui.locateAllOnScreen('./media/page_bubble.png', grayscale=0, region=(left, top+height, 220, screen_height-(top+height)), confidence=confidence)
        pages_offline = positions
    except:
        pages_offline = 0
        print("No offline")
    return len(make_unique_list(list(pages_online) + list(pages_offline)))

def get_friends_on_current_page():
    pyautogui.moveTo(500, 0)
    try:
        return list(pyautogui.locateAllOnScreen('./media/unlit_friend.png', grayscale=1, region=(190, 160, 1691, 948), confidence=confidence))
    except:
        return [] 

def lightFriend(x, y):
    pyautogui.click(x, y)
    time.sleep(.3) # we need this bc the q kinda stays there for a bit
    try:
        q_position = pyautogui.locateOnScreen('./media/q_info.png', grayscale=1, region=(1540, 1025, 30, 30), confidence=confidence)
        pyautogui.click(x, y)
        pyautogui.moveTo(q_position)
        time.sleep(.2)
    except:
        try:
            pyautogui.locateOnScreen('./media/esc.png', grayscale=1, confidence=0.6)
        except:
            enter_ui()
            return
    time.sleep(.9)
    press_key('f')
    time.sleep(.3)
    press_key('esc')
    time.sleep(.3)
    global friend_count
    friend_count += 1

def loop():
    global current_page
    while current_page <= total_pages:
        # this loop helps double check missed friends
        while True:
            friends = make_unique_list(get_friends_on_current_page(), pixel_distance=10)
            if len(friends) == 0:
                break
            for friend in friends:
                x, y = pyautogui.center(friend)
                lightFriend(x, y)
        press_key('c')
        time.sleep(page_transition_time)
        current_page += 1

if __name__ == "__main__":
    print("Starting!!")
    start_time = time.time()
    time.sleep(1)
    try:
        pyautogui.locateOnScreen('./media/esc.png', grayscale=1, confidence=0.6)
    except:
        enter_ui()
    index_to_start()
    total_pages = get_total_pages()
    loop()
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Lit {friend_count} friends in {int(elapsed_time)} seconds")