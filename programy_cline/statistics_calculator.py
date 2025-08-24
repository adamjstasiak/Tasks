import pandas as pd
import argparse
import xml.etree.ElementTree as ET

def calculate_statistics(file_path, column_name):
    """
    Calculates statistics (average, variance, standard deviation) for a given column in a CSV or XML file.

    Args:
        file_path (str): The path to the input file (CSV or XML).
        column_name (str): The name of the column to calculate statistics for.

    Returns:
        dict: A dictionary containing the calculated statistics.
    """
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith('.xml'):
        tree = ET.parse(file_path)
        root = tree.getroot()
        data = []
        for elem in root.findall('.//record'):  # Assuming a simple 'record' structure
            data.append({child.tag: child.text for child in elem})
        df = pd.DataFrame(data)
    else:
        raise ValueError("Unsupported file format. Please provide a .csv or .xml file.")

    if column_name not in df.columns:
        raise ValueError(f"Column '{column_name}' not found in the file.")

    # Convert column to numeric, coercing errors to NaN
    df[column_name] = pd.to_numeric(df[column_name], errors='coerce')
    
    # Drop rows with NaN in the specified column
    df.dropna(subset=[column_name], inplace=True)

    if df.empty:
        raise ValueError(f"No valid numeric data found in column '{column_name}'.")

    # Calculate statistics
    average = df[column_name].mean()
    variance = df[column_name].var()
    std_deviation = df[column_name].std()

    return {
        'average': average,
        'variance': variance,
        'standard_deviation': std_deviation
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate statistics for a column in a CSV or XML file.")
    parser.add_argument("file_path", help="Path to the CSV or XML file.")
    parser.add_argument("column_name", help="Name of the column to analyze.")
    
    args = parser.parse_args()

    try:
        stats = calculate_statistics(args.file_path, args.column_name)
        print(f"Statistics for column '{args.column_name}':")
        for key, value in stats.items():
            print(f"  {key.replace('_', ' ').title()}: {value:.2f}")
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}")
