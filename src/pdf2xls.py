from pathlib import Path
from argparse import ArgumentParser, ArgumentError

import tabula as tb
import pandas as pd
import tabulate as tbl

def pdf2xls(pdf_path:Path, xls_path:Path) -> Path:
    tables = tb.read_pdf(pdf_path, pages='all')

    with pd.ExcelWriter(str(xls_path)) as writer:
        for i, table in enumerate(tables):
            table.to_excel(writer, sheet_name=f'Sheet_{i+1}')
    return xls_path

def pdf2md(input:Path, output:Path) -> Path:
    """
    Using Tabulate and pdfreader convert the pdf to a markdown file table
    """
    tables = tb.read_pdf(input, pages='all')
    with open(output, 'w') as f:
        for i, table in enumerate(tables):
            f.write(tbl.tabulate(table, tablefmt='pipe'))
            f.write('\n\n')
    return output

def txt2csv(input:Path, output:Path) -> Path:
    """
    Parse the text file and convert it to a CSV file via tabs
    """

    with open(input, 'r') as inp:
        print(list(zip(*(line.strip().split('\t') for line in inp))))

    

if __name__ == '__main__':
    parser = ArgumentParser(description='Convert a PDF to an Excel file')
    parser.add_argument('-input', help='Path to the PDF file', required=True, type=Path)
    parser.add_argument('-output', help='Path to save the Excel file', required=True, type=Path)

    args = parser.parse_args()


    try:
        # output = tb.convert_into(str(args.input), str(args.output), output_format='csv', pages='all', stream=True)
        txt2csv(args.input, args.output)
        # df = (args.input)
        # output = (args.output)
        # tb.convert_into(df, output, output_format='csv', stream=True)
        print(f'Excel file saved to {args.output}')
    except ArgumentError as e:
        print(f'Error: {e}')