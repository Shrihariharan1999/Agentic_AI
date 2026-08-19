# Snake and Ladder Game in Python
import random

def play_snake_and_ladder():
    print("Welcome to Snake and Ladder!")
    print("Objective: Reach position 100 by rolling the dice.")
    print("Snakes will slide you down, ladders will climb you up.\n")
    
    # Define snakes and ladders
    snakes = {
        14: 4,
        24: 16,
        35: 15,
        48: 11,
        51: 38,
        64: 60,
        73: 70,
        87: 54,
        93: 77,
        99: 1
    }
    
    ladders = {
        1: 38,
        4: 14,
        8: 31,
        17: 45,
        27: 61,
        39: 77,
        45: 84,
        51: 67,
        63: 87,
        71: 91
    }
    
    current_position = 0
    while current_position < 100:
        input("Press Enter to roll the dice...")
        dice = random.randint(1, 6)
        print(f"You rolled a {dice}\n")
        new_position = current_position + dice
        
        # Check if move exceeds board
        if new_position > 100:
            print(f"You can't move beyond 100. Stay at {current_position}\n")
            continue
        
        # Check for snakes or ladders
        if new_position in snakes:
            print(f"Snake bite! Sliding down from {new_position} to {snakes[new_position]}\n")
            new_position = snakes[new_position]
        elif new_position in ladders:
            print(f"Climbed a ladder from {new_position} to {ladders[new_position]}\n")
            new_position = ladders[new_position]
        
        current_position = new_position
        print(f"Your current position is {current_position}\n")
    
    print("Congratulations! You've reached the end of the board. You win!\n")

if __name__ == "__main__":
    play_snake_and_ladder()