import requests
import defusedxml.ElementTree as ET
from decimal import Decimal
from datetime import datetime, date
import argparse
from decimal import InvalidOperation

def download(url):
    response = requests.get(
        url,
        headers={"User-Agent": "Exchange Data"},
        timeout=10,
    )

    response.raise_for_status()
    return response.content


def parse_tcmb(data):
    root = ET.fromstring(data)

    date = root.attrib.get("Date")
    date = datetime.strptime(date, "%m/%d/%Y").date()

    currencies = root.findall("Currency")
    rates = dict()

    for currency in currencies:

        code = currency.get("Kod")
        unit = currency.findtext("Unit")
        price = currency.findtext("ForexBuying")

        if not price:
            continue

        unit_price = Decimal(price)/Decimal(unit)

        rates[code] = unit_price

    rates["TRY"] = Decimal("1")
    
    return rates, date



def parse_ecb(data):
    root = ET.fromstring(data)

    time = root.find(".//{*}Cube[@time]")
    if time==None:
        raise ValueError("Date is not given in ECB data!")

    time = time.attrib.get("time")
    date.fromisoformat(time)    

    currencies = root.findall(".//{*}Cube[@currency]")
    rates = dict()

    for currency in currencies:
        code = currency.get("currency")
        rate = Decimal(currency.get("rate"))

        rates[code] = rate
    
    rates["EUR"] = Decimal("1")
    
    return rates, time

def convert_directly(rates: dict, amount: Decimal, from_code: str, to_code:str, currency:str):
    if not rates.get(to_code) or not rates.get(from_code):
        raise ValueError("Given currency is not covered in the data!")
    if currency == "EUR":
        if from_code == currency:
            return amount * rates.get(to_code)
        elif to_code == currency:
            return amount * (1/rates.get(from_code))
    elif currency == "TRY":
        if from_code == currency:
            return amount * (1/rates.get(to_code))
        
        elif to_code == currency:
            return amount * rates.get(from_code)

    else:
        raise ValueError("Given currency is not covered in the data!")


def convert_undirectly(rates: dict, amount:Decimal, from_code:str, to_code:str, currency: str):
    
    if not rates.get(to_code):
        raise ValueError("Given currency is not covered in the data!")


    elif not rates.get(from_code):
        raise ValueError("Given currency is not covered in the data!")

    if currency == "EUR":
        rate = (1/rates[from_code]) * (rates[to_code])
    else:
        rate = (1/rates[to_code]) * (rates[from_code])
    return amount * rate

    
def convert_from_tcmb(rates: dict, amount:Decimal, from_code:str, to_code:str):

    answer = convert_directly(rates, amount, from_code, to_code, "TRY")
    return answer

def convert_from_ecb(rates: dict, amount: Decimal, from_code: str, to_code:str):

    answer = convert_directly(rates, amount, from_code, to_code, "EUR")
    return answer

def select_converter(tcmb_dict: dict, ecb_dict: dict, amount: Decimal, from_code:str, to_code:str):
    
    if (from_code == "EUR" or to_code == "EUR") and from_code in ecb_dict.keys() and to_code in ecb_dict.keys():
        return convert_from_ecb(ecb_dict, amount, from_code, to_code)

    elif (from_code == "TRY" or to_code == "TRY") and from_code in tcmb_dict.keys() and to_code in tcmb_dict.keys():
        return convert_from_tcmb(tcmb_dict, amount, from_code, to_code)

    elif from_code in ecb_dict.keys() and to_code in ecb_dict.keys():
        return convert_undirectly(ecb_dict, amount, from_code, to_code, "EUR")

    elif from_code in tcmb_dict.keys() and to_code in tcmb_dict.keys():
        return convert_undirectly(tcmb_dict, amount, from_code, to_code, "TRY")
    else: 
        raise ValueError("Given currency is not covered in the data!")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Get conversion data.")
    parser.add_argument("amount", type=str, help="Currency amount")
    parser.add_argument("from_code", type=str, help="Code of the currency to convert.")
    parser.add_argument("to_code", type=str, help="Code of the currency to convert into.")
    args = parser.parse_args()

    tcmb_data = download("https://www.tcmb.gov.tr/kurlar/today.xml")
    ecb_data = download("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml")

    tcmb_dict, tcmb_date = parse_tcmb(tcmb_data)

    ecb_dict, ecb_date = parse_ecb(ecb_data)
    try:
        amount = Decimal(args.amount)
        result = select_converter(tcmb_dict, ecb_dict, amount, args.from_code.upper(), args.to_code.upper())
        print(result.quantize(Decimal("0.01")))
    except ValueError as e:
        print("Given currencies may not be in the list!")
    except InvalidOperation:
        parser.error(f"not a number: {args.amount}")
    
    

    