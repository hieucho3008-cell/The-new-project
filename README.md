# Hand Dexterity Assessment System

## Overview

This project is a computer vision-based rehabilitation assessment tool developed using Python, OpenCV, and MediaPipe.

The system evaluates hand dexterity by tracking repetitive hand opening and closing movements through a webcam. It automatically measures repetition count, exercise duration, and movement speed, providing objective feedback for rehabilitation monitoring.

---

## Features

- Real-time hand tracking
- Finger counting
- Open-hand / closed-hand detection
- Repetition counting
- Speed calculation
- Performance statistics
- CSV data export

---

## Technologies Used

- Python
- OpenCV
- MediaPipe
- NumPy
- Pandas

---

## Installation

pip install -r requirements.txt

---

## Run

python main.py

---

## Workflow

1. Capture webcam frames
2. Detect hand landmarks
3. Count raised fingers
4. Detect open/closed hand state
5. Count repetitions
6. Calculate exercise statistics
7. Save results

---

## Project Structure

main.py
hand_detector.py
finger_counter.py
exercise_logic.py
statistics.py

---

## Future Work

- Tremor detection
- Rehabilitation scoring
- Patient database
- Mobile deployment
