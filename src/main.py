import cv2
import time

from hand_detector import HandDetector
from finger_counter import count_fingers
from exercise_logic import DexterityExercise
from statistics import Statistics

# ==========================
# CAMERA
# ==========================

cap = cv2.VideoCapture(0)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# ==========================
# OBJECTS
# ==========================

detector = HandDetector()
exercise = DexterityExercise()
stats = Statistics()

# ==========================
# SESSION VARIABLES
# ==========================

test_started = False
paused = False
finished = False

MAX_TIME = 60

pause_start = 0
total_pause_time = 0
elapsed_before_pause = 0

last_result = "No previous session"

session_history = []

# ==========================
# MAIN LOOP
# ==========================

while True:

    success, img = cap.read()

    if not success:
        break

    img = cv2.flip(img, 1)

    hands, img = detector.find_hands(img)

    # ==========================
    # HAND DETECTION
    # ==========================

    finger_count = 0
    left_count = 0
    right_count = 0

    if len(hands) > 0:

        for hand in hands:

            fingers = count_fingers(hand)

            finger_count += fingers

            if hand["type"] == "Left":
                left_count = fingers

            elif hand["type"] == "Right":
                right_count = fingers

        if test_started and not paused:
            exercise.update(finger_count)

    # ==========================
    # TIMER
    # ==========================

    if test_started and not paused:

        elapsed = (
            time.time()
            - stats.start_time
            - total_pause_time
        )

    elif paused:

        elapsed = elapsed_before_pause

    else:

        elapsed = 0

    remaining_time = max(
        0,
        MAX_TIME - int(elapsed)
    )

    # ==========================
    # SPEED
    # ==========================

    if exercise.repetitions > 0:
        speed = elapsed / exercise.repetitions
    else:
        speed = 0

    # ==========================
    # AUTO FINISH
    # ==========================

    if remaining_time == 0 and test_started:

        paused = True
        test_started = False
        finished = True

        session_history.append({
          "reps": exercise.repetitions,
          "speed": speed
        })

    last_result = (
        f"Last Session: "
        f"{exercise.repetitions} reps | "
        f"{speed:.2f} sec/cycle"
    )
    if len(session_history) > 0:

        avg_reps = sum(
            s["reps"]
            for s in session_history
        ) / len(session_history)

    avg_speed = sum(
        s["speed"]
        for s in session_history
    ) / len(session_history)

    best_reps = max(
        s["reps"]
        for s in session_history
    )

else:

    avg_reps = 0
    avg_speed = 0
    best_reps = 0

    # ==========================
    # SESSION STATUS
    # ==========================

    if finished:

        session_status = "FINISHED"

    elif not test_started and elapsed == 0:

        session_status = "READY"

    elif paused:

        session_status = "PAUSED"

    else:

        session_status = "RUNNING"

    # ==========================
    # HAND STATUS
    # ==========================

    if finger_count >= 4:

        status = "OPEN"
        color = (0, 255, 0)

    elif finger_count <= 1:

        status = "CLOSED"
        color = (0, 0, 255)

    else:

        status = "MOVING"
        color = (0, 255, 255)

    # ==========================
    # UI PANEL
    # ==========================

    cv2.putText(
        img,
        "HAND DEXTERITY ASSESSMENT",
        (35, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 0, 0),
        2
    )

    cv2.putText(
        img,
        f"Left Hand : {left_count}",
        (35, 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 0),
        2
    )

    cv2.putText(
        img,
        f"Right Hand : {right_count}",
        (35, 160),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 0),
        2
    )

    cv2.putText(
        img,
        f"Total Fingers : {finger_count}",
        (35, 210),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 0, 0),
        2
    )

    cv2.putText(
        img,
        f"Status : {status}",
        (35, 260),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        color,
        3
    )

    cv2.putText(
        img,
        f"Repetitions : {exercise.repetitions}",
        (35, 310),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 255),
        2
    )

    cv2.putText(
        img,
        f"Session : {session_status}",
        (35, 360),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 0, 0),
        2
    )

    cv2.putText(
        img,
        f"Time Left : {remaining_time} sec",
        (35, 410),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 0, 255),
        2
    )

    cv2.putText(
        img,
        f"Avg Speed : {speed:.2f} sec/cycle",
        (35, 460),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 120, 255),
        2
    )

    cv2.putText(
        img,
        last_result,
        (35, 510),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (120, 0, 255),
        2
    )
    cv2.putText(
    img,
    f"Sessions : {len(session_history)}",
    (35,540),
    cv2.FONT_HERSHEY_SIMPLEX,
    0.6,
    (0,0,0),
    2
    )

    cv2.putText(
    img,
    f"Avg Reps : {avg_reps:.1f}",
    (35,570),
    cv2.FONT_HERSHEY_SIMPLEX,
    0.6,
    (0,150,0),
    2
    )

    cv2.putText(
    img,
    f"Avg Speed : {avg_speed:.2f}",
    (35,600),
    cv2.FONT_HERSHEY_SIMPLEX,
    0.6,
    (150,0,150),
    2
    )

    cv2.putText(
    img,
    f"Best Reps : {best_reps}",
    (35,630),
    cv2.FONT_HERSHEY_SIMPLEX,
    0.6,
    (255,0,0),
    2
    )

    # ==========================
    # CONTROLS
    # ==========================

    cv2.putText(
        img,
        "B = Start",
        (850, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.putText(
        img,
        "P = Pause / Resume",
        (850, 150),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2
    )

    cv2.putText(
        img,
        "R = Reset",
        (850, 200),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 0, 0),
        2
    )

    cv2.putText(
        img,
        "ESC = Exit",
        (850, 250),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 255),
        2
    )

    # ==========================
    # WINDOW
    # ==========================

    cv2.namedWindow(
        "Hand Dexterity Assessment",
        cv2.WINDOW_NORMAL
    )

    cv2.resizeWindow(
        "Hand Dexterity Assessment",
        1280,
        720
    )

    cv2.imshow(
        "Hand Dexterity Assessment",
        img
    )

    # ==========================
    # KEYBOARD
    # ==========================

    key = cv2.waitKey(1)

    if key == ord('b') and not test_started:

        test_started = True
        paused = False
        finished = False

        stats.start_time = time.time()

        total_pause_time = 0

    elif key == ord('p'):

        if test_started:

            if not paused:

                paused = True

                pause_start = time.time()

                elapsed_before_pause = elapsed

            else:

                paused = False

                total_pause_time += (
                    time.time() - pause_start
                )

    elif key == ord('r'):

        exercise.repetitions = 0

        test_started = False
        paused = False
        finished = False

        total_pause_time = 0

        last_result = "No previous session"

    elif key == 27:

            break

# ==========================
# EXIT
# ==========================

cap.release()
cv2.destroyAllWindows()
