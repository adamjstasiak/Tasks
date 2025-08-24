import math

def add(x, y):
    return x + y

def subtract(x, y):
    return x - y

def multiply(x, y):
    return x * y

def divide(x, y):
    if y == 0:
        return "Error! Division by zero."
    return x / y

def power(x, y):
    return x ** y

def root(x, y):
    if x < 0 and y % 2 == 0:
        return "Error! Root of a negative number with an even index."
    return x ** (1/y)

def main():
    while True:
        print("Select operation:")
        print("1.Add")
        print("2.Subtract")
        print("3.Multiply")
        print("4.Divide")
        print("5.Power")
        print("6.Root")
        print("7.Exit")

        choice = input("Enter choice(1/2/3/4/5/6/7): ")

        if choice in ('1', '2', '3', '4', '5', '6'):
            try:
                num1 = float(input("Enter first number: "))
                num2 = float(input("Enter second number: "))
            except ValueError:
                print("Invalid input. Please enter a number.")
                continue

            if choice == '1':
                print(num1, "+", num2, "=", add(num1, num2))

            elif choice == '2':
                print(num1, "-", num2, "=", subtract(num1, num2))

            elif choice == '3':
                print(num1, "*", num2, "=", multiply(num1, num2))

            elif choice == '4':
                print(num1, "/", num2, "=", divide(num1, num2))
            
            elif choice == '5':
                print(num1, "^", num2, "=", power(num1, num2))

            elif choice == '6':
                print(num1, "root", num2, "=", root(num1, num2))

        elif choice == '7':
            break
        else:
            print("Invalid input")

if __name__ == "__main__":
    main()
