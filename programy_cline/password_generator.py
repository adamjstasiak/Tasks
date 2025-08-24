import random
import string

def generate_password(length):
    """
    Generates a secure password of a specified length using letters, numbers, and special characters.
    """
    if length < 1:
        raise ValueError("Password length must be at least 1.")

    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for i in range(length))
    return password

if __name__ == "__main__":
    try:
        password_length = int(input("Enter the desired password length: "))
        secure_password = generate_password(password_length)
        print(f"Generated secure password: {secure_password}")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
