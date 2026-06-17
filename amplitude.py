import math

def calculate_amplitude(hand):

    lmList = hand["lmList"]

    thumb = lmList[4]
    pinky = lmList[20]

    distance = math.sqrt(
        (thumb[0] - pinky[0])**2 +
        (thumb[1] - pinky[1])**2
    )

    return distance
