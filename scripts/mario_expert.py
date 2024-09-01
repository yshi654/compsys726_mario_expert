import json
import logging
import random
import time

import cv2
from mario_environment import MarioEnvironment
from pyboy.utils import WindowEvent


class MarioController(MarioEnvironment):
    def __init__(
            self,
            act_freq: int = 10,
            emulation_speed: int = 0,
            headless: bool = False,
    ) -> None:
        # Initialize the base MarioEnvironment class with specific parameters.
        super().__init__(
            act_freq=act_freq,
            emulation_speed=emulation_speed,
            headless=headless,
        )

        self.act_freq = act_freq  # Frequency at which actions are performed.

        # Map of valid actions that can be sent to the PyBoy emulator.
        valid_actions: list[WindowEvent] = [
            WindowEvent.PRESS_ARROW_DOWN,
            WindowEvent.PRESS_ARROW_LEFT,
            WindowEvent.PRESS_ARROW_RIGHT,
            WindowEvent.PRESS_ARROW_UP,
            WindowEvent.PRESS_BUTTON_A,
            WindowEvent.PRESS_BUTTON_B,
        ]

        # Map of actions to release the button press in the PyBoy emulator.
        release_button: list[WindowEvent] = [
            WindowEvent.RELEASE_ARROW_DOWN,
            WindowEvent.RELEASE_ARROW_LEFT,
            WindowEvent.RELEASE_ARROW_RIGHT,
            WindowEvent.RELEASE_ARROW_UP,
            WindowEvent.RELEASE_BUTTON_A,
            WindowEvent.RELEASE_BUTTON_B,
        ]

        self.valid_actions = valid_actions  # Store the valid actions.
        self.release_button = release_button  # Store the release actions.

    def run_action(self, action: int) -> None:
        # Handle running jump actions specifically.
        if action == 6:  # If the action is a "run jump".
            # Send the command to press the right arrow and the button A.
            self.pyboy.send_input(self.valid_actions[2])  # Right arrow
            self.pyboy.send_input(self.valid_actions[4])  # Button A
            # Continue the action for a number of ticks defined by act_freq.
            for _ in range(self.act_freq):
                self.pyboy.tick()
            # Release the buttons after the action duration.
            self.pyboy.send_input(self.release_button[2])  # Release right arrow
            self.pyboy.send_input(self.release_button[4])  # Release button A
            # Ensure the game state advances by the same number of ticks.
            for _ in range(self.act_freq):
                self.pyboy.tick()
        elif action == 7:  # If the action is a "long jump".
            # Similar to a running jump but held for three times longer.
            self.pyboy.send_input(self.valid_actions[2])  # Right arrow
            self.pyboy.send_input(self.valid_actions[4])  # Button A
            for _ in range(self.act_freq * 3):
                self.pyboy.tick()
            self.pyboy.send_input(self.release_button[2])  # Release right arrow
            self.pyboy.send_input(self.release_button[4])  # Release button A
            for _ in range(self.act_freq):
                self.pyboy.tick()
        else:
            # For all other actions, press and release the corresponding button.
            self.pyboy.send_input(self.valid_actions[action])
            for _ in range(self.act_freq):
                self.pyboy.tick()
            self.pyboy.send_input(self.release_button[action])
            # For Button A press, add an extra tick for potential game response time.
            if action == 4:
                self.pyboy.tick()


class MarioExpert:

    def __init__(self, results_path: str, headless=False):
        self.results_path = results_path

        self.environment = MarioController(headless=headless)

        self.video = None

    def choose_action(self):
        state = self.environment.game_state()
        frame = self.environment.grab_frame()
        game_area = self.environment.game_area()
        # Implement your code here to choose the best action
        # Constants for actions and entities in the game
        DOWN,LEFT,RIGHT,UP = 0,1,2,3
        BUTTON_A,BUTTON_B,RUN_JUMP,LONG_JUMP = 4,5,6,7
        # Constants for objects in the game environment
        HOLE,MARIO,COIN,MUSHROOM,HILL,BLOCK,BOX,PIPE = 0,1,5,6,10,12,13,14
        ENEMY_CHIBIBO = 15
        ENEMY_NOKOBON = 16
        ENEMY_SUU = 17
        ENEMY_KUMO = 18
        # Initialize Mario's position and related variables
        (mario_x,mario_y,enemy_x,enemy_y,enemy_type,
         mushroom_x,mushroom_y,box_x,box_y,coin_y,coin_x) = 0,0,0,0,0,0,0,0,0,0,0
        # Convert the game area into a list for processing
        game_area_list = game_area.tolist()
        game_area_list_t = game_area.T.tolist()
        # Locate Mario in the grid
        x_list = [x for x in game_area_list if MARIO in x]
        if x_list != []:
            x = x_list[0]
            mario_x = game_area_list.index(x)
            mario_y = x.index(MARIO)
        else:
            return 0 # No action if Mario is not found
        # Search for mushrooms in the grid
        x_list = [x for x in game_area_list if MUSHROOM in x]
        if x_list != []:
            x = x_list[0]
            mushroom_x = game_area_list.index(x)
            mushroom_y = x.index(MUSHROOM)
        else:
            mushroom_x = -1
            mushroom_y = -1
        # Analyze the grid for enemies in Mario's row
        enemy_list_t = game_area_list_t[mario_y:]
        x_list = [x for x in enemy_list_t if ENEMY_CHIBIBO in x or ENEMY_NOKOBON in x or ENEMY_SUU in x or ENEMY_KUMO in x]

        if x_list != []:
            x = x_list[0]
            enemy_y = enemy_list_t.index(x) + mario_y
            y_list = [y for y in x if y >= ENEMY_CHIBIBO and y <= ENEMY_KUMO]
            enemy_x = x.index(y_list[0])
            enemy_type = y_list[0]
        else:
            enemy_type = 0
        # Identify boxes within the transposed grid
        x_list = [x for x in game_area_list_t if BOX in x]
        if x_list != []:
            x = x_list[0]
            box_y = game_area_list_t.index(x)
            box_x = x.index(BOX)
        else:
            box_y = -1
            box_x = -1
        # Check for coins
        x_list = [x for x in game_area_list_t if COIN in x]
        if x_list != []:
            x = x_list[0]
            coin_y = game_area_list_t.index(x)
            coin_x = len(x) - 1 - x[::-1].index(COIN)
        else:
            coin_y = -1
            coin_x = -1

        # Decide on actions based on game entity positions and states
        # enemy is able to fly, need a long jump
        if enemy_type == ENEMY_KUMO:
            if (mario_x == enemy_x) and ((mario_y + 2 == enemy_y) or (mario_y + 3 == enemy_y)):
                return LONG_JUMP

        # enemy is falling from above, turn left to avoid
        if (mario_x >= enemy_x + 1) and (mario_x <= enemy_x + 3) and (mario_y < enemy_y) and (mario_y + 4 >= enemy_y):
            return LEFT

        # enemy is not able to fly, jump to skip or step
        if enemy_type != ENEMY_KUMO:
            if (mario_x + 1 == enemy_x or mario_x == enemy_x) and mario_y + 4 >= enemy_y and mario_y <= enemy_y:
                return BUTTON_A

        # mario on ground level and a hole ahead
        if (mario_y <= 15):
            if mario_x == 12 and (game_area[14][mario_y + 2] == HOLE or game_area[14][mario_y + 3] == HOLE):
                return LONG_JUMP

        # There is a mushroom on the left
        if mushroom_y != -1 and mushroom_y < mario_y:
            return LEFT

        if mario_x <= 14 and mario_y <= 16:

            # There is a long pipe blocking the road
            if game_area[mario_x - 2][mario_y + 1] == PIPE or game_area[mario_x - 2][mario_y + 2] == PIPE:
                return LONG_JUMP

            # There is a pipe blocking the road
            if game_area[mario_x + 1][mario_y + 2] == PIPE:
                return RUN_JUMP

            # It is a blocked tunnel and need to go back
            if (game_area[mario_x][mario_y + 2] == HILL or game_area[mario_x + 1][mario_y + 2] == HILL) and (
                    game_area[mario_x - 1][mario_y + 1] == HILL or game_area[mario_x - 1][mario_y + 2] == HILL or
                    game_area[mario_x + 1][mario_y + 2] == HILL) and (game_area[mario_x + 1][mario_y + 2] == HOLE):
                return LEFT

                # A hill ahead and need to jump
            if game_area[mario_x][mario_y + 2] == HILL or game_area[mario_x + 1][mario_y + 2] == HILL:
                return LONG_JUMP

            # if there is a block blocking ahead, jump
            if (game_area[mario_x][mario_y + 2] == BLOCK or game_area[mario_x + 1][mario_y + 2] == BLOCK):
                return BUTTON_A

        # if mario is above the ground and there is a coin somewhere below
        if (mario_x < 12) and (mario_x < coin_x - 1):
            if mario_y == coin_y - 2:
                return DOWN
            if mario_y > coin_y - 2 and game_area[coin_x - 1][coin_y] != HILL:
                return LEFT

        # mario on high level and a hole ahead
        if (mario_y <= 12):

            if mario_x < 12 and game_area[mario_x + 2][mario_y] != 0:
                if (game_area[14][mario_y + 3] == HOLE or game_area[14][mario_y + 4] == HOLE or game_area[14][
                    mario_y + 5] == HOLE):
                    if game_area[mario_x - 2][mario_y + 1] == 0:
                        return LONG_JUMP

        if (box_x != -1):
            # if there is a ? box above the ground level and on the left, move left
            if (mario_x > box_x and mario_x <= box_x + 3) and game_area[mario_x + 1][mario_y - 1] == 0:
                if box_y <= mario_y:
                    return LEFT

        # if there is a ? box above the ground level and on the right ahead, jump
        if mario_x > box_x and mario_x <= box_x + 3 and mario_y < box_y and mario_y + 1 >= box_y:
            return BUTTON_A

        # move forward
        return RIGHT

    def step(self):

        # Choose an action - button press or other...
        action = self.choose_action()

        # Run the action on the environment
        self.environment.run_action(action)

    def play(self):
        """
        Do NOT edit this method.
        """
        self.environment.reset()

        frame = self.environment.grab_frame()
        height, width, _ = frame.shape

        self.start_video(f"{self.results_path}/mario_expert.mp4", width, height)

        while not self.environment.get_game_over():
            frame = self.environment.grab_frame()
            self.video.write(frame)

            self.step()

        final_stats = self.environment.game_state()
        logging.info(f"Final Stats: {final_stats}")

        with open(f"{self.results_path}/results.json", "w", encoding="utf-8") as file:
            json.dump(final_stats, file)

        self.stop_video()

    def start_video(self, video_name, width, height, fps=30):
        """
        Do NOT edit this method.
        """
        self.video = cv2.VideoWriter(
            video_name, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )

    def stop_video(self) -> None:
        """
        Do NOT edit this method.
        """
        self.video.release()
