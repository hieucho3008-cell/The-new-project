def count_fingers(hand):

    lmList = hand["lmList"]

    tips = [4, 8, 12, 16, 20]

    count = 0

    if lmList[4][0] > lmList[3][0]:
        count += 1

    for tip in tips[1:]:

        if lmList[tip][1] < lmList[tip - 2][1]:
            count += 1

    return count
