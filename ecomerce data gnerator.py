#!/usr/bin/env python3
"""
ecommerce_data_generator.py  (v2 -- realism upgrade)
=====================================================
Single-file synthetic e-commerce dataset generator.

Changes vs v1 (per review feedback):
  1. Customer attributes are no longer independent random draws. They are
     built in a strict dependency chain:
         Gender -> Name -> Country -> State -> City -> Postal_Code
         -> Phone_Number -> Currency
     Each step is sampled conditionally on the previous ones, so e.g. a
     "France" customer always gets a French city/state/postcode/phone/EUR.
  2. Faker has been REMOVED entirely. Cities, states, postal codes and
     phone numbers now come from small, curated, country-accurate lookup
     tables instead of a generic locale library -- this also eliminates
     Faker artifacts like phone extensions ("x3682").
  3. First names are drawn from country-specific MALE/FEMALE name banks,
     so gender and name are always consistent (e.g. "Richard" -> Male).
  4. Phone numbers use hand-written, country-specific formatting
     functions (no extensions, correct grouping/country code).
  5. Customers now have real purchase HISTORY: each customer gets a
     number of orders derived from their segment's annual order-rate and
     their tenure, not a per-row random resample. Segments:
         Regular : 1-3 orders/year
         Loyal   : 4-10 orders/year
         VIP     : 10-25 orders/year
     Total row count is therefore an emergent property of the simulation,
     not a fixed input (config.n_records is used only to size the initial
     customer pool -- the final printed count will differ, by design).
  6. The product catalog now uses realistic, recognizable product names
     (Apple iPhone 15, Samsung Galaxy S24, Nike Air Max, Sony Headphones,
     Dell Laptop, etc.) with simple, price-adjusting variants
     (storage / color / size) instead of generic templated names.
  7. Extra validation: geo-consistency (Country/State/City triples must
     be one of the known, real combinations), phone-format sanity (no
     stray "x" extensions), plus all the original financial/date checks.

Run:  python ecommerce_data_generator.py
Outputs: ecommerce_dataset.csv (+ .parquet / .xlsx if libs available)
"""

import logging
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import os

os.chdir(r"d:\my multiple projects\end to end ecomerce sales project")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s",
                     datefmt="%H:%M:%S")
logger = logging.getLogger("ecommerce_generator")

# ====================================================================== #
# CONFIG -- edit these values, then just run the script
# ====================================================================== #
@dataclass
class Config:
    n_records: int = 100_000              # TARGET row count, used only to size the
                                           # customer pool -- actual output row count
                                           # emerges from per-customer purchase history
                                           # and will differ from this number.
    n_customers: int = 0                  # 0 = auto-derive from n_records
    n_products: int = 1_200
    random_seed: int = 42

    start_date: date = date(2023, 1, 1)
    end_date: date = date(2025, 12, 31)

    output_dir: str = "output"
    output_basename: str = "ecommerce_dataset"
    output_formats: Tuple[str, ...] = ("csv", "parquet")   # add "xlsx" if wanted

    missing_value_pct_range: Tuple[float, float] = (0.10, 0.15)
    duplicate_pct_range: Tuple[float, float] = (0.05, 0.09)

    # Segment mix and annual order-rate ranges (orders per year, per customer).
    segment_probs: Dict[str, float] = None
    segment_orders_per_year: Dict[str, Tuple[int, int]] = None

    nullable_columns: Tuple[str, ...] = (
        "Phone_Number", "Postal_Code", "Discount_Percentage", "Coupon_Code",
        "Customer_Rating", "Review_Count", "Return_Reason", "Device_Type",
        "Traffic_Source", "Seller_Name", "Shipping_Date", "Delivery_Date",
        "Session_ID",
    )

    def __post_init__(self):
        if self.segment_probs is None:
            self.segment_probs = {"Regular": 0.65, "Loyal": 0.25, "VIP": 0.10}
        if self.segment_orders_per_year is None:
            self.segment_orders_per_year = {"Regular": (1, 3), "Loyal": (4, 10), "VIP": (10, 25)}


CONFIG = Config()
# ====================================================================== #


# ------------------------------------------------------------------ #
# Country reference data: currency, tax, cities (city -> state, postal
# prefix), and a phone-number formatter. This REPLACES Faker entirely for
# geography/contact fields, so every value is guaranteed locale-correct
# and there is no risk of Faker-style artifacts (e.g. "x1234" extensions).
# ------------------------------------------------------------------ #
def _us_phone(rng):
    return f"+1-{rng.integers(200, 999)}-{rng.integers(200, 999)}-{rng.integers(1000, 9999)}"


def _uk_phone(rng, area):
    return f"+44-{area}-{rng.integers(1000, 9999)}-{rng.integers(1000, 9999)}"


def _ca_phone(rng, area):
    return f"+1-{area}-{rng.integers(200, 999)}-{rng.integers(1000, 9999)}"


def _au_phone(rng, area):
    return f"+61-{area}-{rng.integers(1000, 9999)}-{rng.integers(1000, 9999)}"


def _de_phone(rng, area):
    return f"+49-{area}-{rng.integers(1000000, 9999999)}"


def _fr_phone(rng):
    return f"+33-{rng.integers(1, 9)}-{rng.integers(10, 99)}-{rng.integers(10, 99)}-{rng.integers(10, 99)}-{rng.integers(10, 99)}"


def _in_phone(rng):
    return f"+91-{rng.integers(70000, 99999)}-{rng.integers(10000, 99999)}"


def _br_phone(rng, area):
    return f"+55-{area}-9{rng.integers(1000, 9999)}-{rng.integers(1000, 9999)}"


def _jp_phone(rng, area):
    return f"+81-{area}-{rng.integers(1000, 9999)}-{rng.integers(1000, 9999)}"


def _pk_phone(rng):
    return f"+92-3{rng.integers(0, 9)}{rng.integers(0, 9)}-{rng.integers(1000000, 9999999)}"


# Each city entry: (city_name, state/province, postal_prefix, phone_area_code)
COUNTRY_DATA = {
    "United States": {
        "currency": "USD", "tax": 0.075,
        "cities": [
            ("New York", "New York", "100", None), ("Los Angeles", "California", "900", None),
            ("Chicago", "Illinois", "606", None), ("Houston", "Texas", "770", None),
            ("Phoenix", "Arizona", "850", None), ("Miami", "Florida", "331", None),
        ],
        "postal_fn": lambda rng, prefix: f"{prefix}{rng.integers(0, 99):02d}",
        "phone_fn": lambda rng, area: _us_phone(rng),
        "male_names": ["James", "Robert", "John", "Michael", "David", "William", "Richard", "Joseph", "Thomas", "Charles"],
        "female_names": ["Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"],
        "last_names": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"],
    },
    "United Kingdom": {
        "currency": "GBP", "tax": 0.20,
        "cities": [
            ("London", "England", "SW1", "20"), ("Manchester", "England", "M1", "161"),
            ("Birmingham", "England", "B1", "121"), ("Leeds", "England", "LS1", "113"),
            ("Glasgow", "Scotland", "G1", "141"),
        ],
        "postal_fn": lambda rng, prefix: f"{prefix} {rng.integers(1, 9)}{random.choice('ABCDEFGH')}{random.choice('ABCDEFGH')}",
        "phone_fn": lambda rng, area: _uk_phone(rng, area),
        "male_names": ["Oliver", "George", "Harry", "Jack", "Jacob", "Noah", "Charlie", "Thomas", "Oscar", "William"],
        "female_names": ["Olivia", "Amelia", "Isla", "Ava", "Emily", "Sophia", "Grace", "Lily", "Freya", "Poppy"],
        "last_names": ["Smith", "Jones", "Taylor", "Williams", "Brown", "Davies", "Evans", "Wilson", "Thomas", "Roberts"],
    },
    "Canada": {
        "currency": "CAD", "tax": 0.13,
        "cities": [
            ("Toronto", "Ontario", "M5H", "416"), ("Vancouver", "British Columbia", "V6B", "604"),
            ("Montreal", "Quebec", "H3B", "514"), ("Calgary", "Alberta", "T2P", "403"),
            ("Ottawa", "Ontario", "K1P", "613"),
        ],
        "postal_fn": lambda rng, prefix: f"{prefix} {rng.integers(1, 9)}{random.choice('ABCDEFGH')}{rng.integers(1, 9)}",
        "phone_fn": lambda rng, area: _ca_phone(rng, area),
        "male_names": ["Liam", "Noah", "Ethan", "Lucas", "Mason", "Logan", "James", "Benjamin", "Jacob", "William"],
        "female_names": ["Emma", "Olivia", "Ava", "Sophia", "Charlotte", "Mia", "Amelia", "Harper", "Evelyn", "Abigail"],
        "last_names": ["Smith", "Brown", "Tremblay", "Martin", "Roy", "Wilson", "MacDonald", "Taylor", "Campbell", "Anderson"],
    },
    "Australia": {
        "currency": "AUD", "tax": 0.10,
        "cities": [
            ("Sydney", "New South Wales", "2000", "2"), ("Melbourne", "Victoria", "3000", "3"),
            ("Brisbane", "Queensland", "4000", "7"), ("Perth", "Western Australia", "6000", "8"),
            ("Adelaide", "South Australia", "5000", "8"),
        ],
        "postal_fn": lambda rng, prefix: f"{int(prefix) + rng.integers(0, 99):04d}",
        "phone_fn": lambda rng, area: _au_phone(rng, area),
        "male_names": ["Jack", "William", "Noah", "Thomas", "James", "Oliver", "Lucas", "Henry", "Ethan", "Alexander"],
        "female_names": ["Charlotte", "Olivia", "Amelia", "Ava", "Mia", "Isla", "Grace", "Chloe", "Zoe", "Ruby"],
        "last_names": ["Smith", "Jones", "Williams", "Brown", "Wilson", "Taylor", "Nguyen", "Anderson", "White", "Martin"],
    },
    "Germany": {
        "currency": "EUR", "tax": 0.19,
        "cities": [
            ("Berlin", "Berlin", "10", "30"), ("Munich", "Bavaria", "80", "89"),
            ("Hamburg", "Hamburg", "20", "40"), ("Frankfurt", "Hesse", "60", "69"),
            ("Cologne", "North Rhine-Westphalia", "50", "221"),
        ],
        "postal_fn": lambda rng, prefix: f"{prefix}{rng.integers(100, 999)}",
        "phone_fn": lambda rng, area: _de_phone(rng, area),
        "male_names": ["Maximilian", "Alexander", "Paul", "Leon", "Felix", "Lukas", "Jonas", "David", "Niklas", "Tim"],
        "female_names": ["Marie", "Sophie", "Maria", "Anna", "Emma", "Mia", "Hannah", "Lea", "Lena", "Laura"],
        "last_names": ["Muller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Schulz", "Hoffmann"],
    },
    "France": {
        "currency": "EUR", "tax": 0.20,
        "cities": [
            ("Paris", "Ile-de-France", "75", None), ("Lyon", "Auvergne-Rhone-Alpes", "69", None),
            ("Marseille", "Provence-Alpes-Cote d'Azur", "13", None), ("Toulouse", "Occitanie", "31", None),
            ("Nice", "Provence-Alpes-Cote d'Azur", "06", None),
        ],
        "postal_fn": lambda rng, prefix: f"{prefix}{rng.integers(100, 999)}",
        "phone_fn": lambda rng, area: _fr_phone(rng),
        "male_names": ["Jean", "Pierre", "Michel", "Louis", "Nicolas", "Antoine", "Julien", "Thomas", "Alexandre", "Mathieu"],
        "female_names": ["Marie", "Nathalie", "Isabelle", "Sophie", "Camille", "Claire", "Julie", "Sarah", "Charlotte", "Emilie"],
        "last_names": ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand", "Leroy", "Moreau"],
    },
    "India": {
        "currency": "INR", "tax": 0.18,
        "cities": [
            ("Delhi", "Delhi", "110", None), ("Mumbai", "Maharashtra", "400", None),
            ("Bangalore", "Karnataka", "560", None), ("Hyderabad", "Telangana", "500", None),
            ("Chennai", "Tamil Nadu", "600", None), ("Kolkata", "West Bengal", "700", None),
        ],
        "postal_fn": lambda rng, prefix: f"{prefix}{rng.integers(100, 999)}",
        "phone_fn": lambda rng, area: _in_phone(rng),
        "male_names": ["Raj", "Amit", "Vikram", "Arjun", "Rahul", "Sanjay", "Vijay", "Anil", "Suresh", "Ravi"],
        "female_names": ["Priya", "Anita", "Sunita", "Pooja", "Neha", "Kavita", "Deepa", "Meena", "Sneha", "Shreya"],
        "last_names": ["Sharma", "Verma", "Gupta", "Kumar", "Singh", "Patel", "Reddy", "Rao", "Iyer", "Nair"],
    },
    "Brazil": {
        "currency": "BRL", "tax": 0.17,
        "cities": [
            ("Sao Paulo", "Sao Paulo", "01", "11"), ("Rio de Janeiro", "Rio de Janeiro", "20", "21"),
            ("Brasilia", "Distrito Federal", "70", "61"), ("Salvador", "Bahia", "40", "71"),
            ("Belo Horizonte", "Minas Gerais", "30", "31"),
        ],
        "postal_fn": lambda rng, prefix: f"{prefix}{rng.integers(100, 999)}-{rng.integers(100, 999)}",
        "phone_fn": lambda rng, area: _br_phone(rng, area),
        "male_names": ["Joao", "Pedro", "Lucas", "Gabriel", "Matheus", "Rafael", "Gustavo", "Bruno", "Felipe", "Thiago"],
        "female_names": ["Maria", "Ana", "Julia", "Beatriz", "Camila", "Fernanda", "Larissa", "Amanda", "Leticia", "Patricia"],
        "last_names": ["Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves", "Pereira", "Lima", "Gomes"],
    },
    "Japan": {
        "currency": "JPY", "tax": 0.10,
        "cities": [
            ("Tokyo", "Tokyo", "100", "3"), ("Osaka", "Osaka", "530", "6"),
            ("Yokohama", "Kanagawa", "220", "45"), ("Nagoya", "Aichi", "450", "52"),
            ("Sapporo", "Hokkaido", "060", "11"),
        ],
        "postal_fn": lambda rng, prefix: f"{prefix}-{rng.integers(1000, 9999)}",
        "phone_fn": lambda rng, area: _jp_phone(rng, area),
        "male_names": ["Haruto", "Yuto", "Sota", "Ren", "Riku", "Yuki", "Kaito", "Sora", "Hayato", "Daiki"],
        "female_names": ["Yui", "Aoi", "Hina", "Sakura", "Yuna", "Rin", "Mei", "Koharu", "Akari", "Miyu"],
        "last_names": ["Sato", "Suzuki", "Takahashi", "Tanaka", "Watanabe", "Ito", "Yamamoto", "Nakamura", "Kobayashi", "Kato"],
    },
    "Pakistan": {
        "currency": "PKR", "tax": 0.17,
        "cities": [
            ("Karachi", "Sindh", "74", None), ("Lahore", "Punjab", "54", None),
            ("Islamabad", "Islamabad Capital Territory", "44", None),
            ("Faisalabad", "Punjab", "38", None), ("Rawalpindi", "Punjab", "46", None),
        ],
        "postal_fn": lambda rng, prefix: f"{prefix}{rng.integers(100, 999)}",
        "phone_fn": lambda rng, area: _pk_phone(rng),
        "male_names": ["Muhammad", "Ahmed", "Ali", "Hassan", "Bilal", "Usman", "Imran", "Kashif", "Faisal", "Tariq"],
        "female_names": ["Ayesha", "Fatima", "Sana", "Sara", "Amna", "Hira", "Zainab", "Mahnoor", "Rabia", "Sadia"],
        "last_names": ["Khan", "Ahmed", "Malik", "Hussain", "Shah", "Butt", "Qureshi", "Chaudhry", "Raza", "Iqbal"],
    },
}
COUNTRIES = list(COUNTRY_DATA.keys())
# Bigger, more mature e-commerce markets get proportionally more customers.
COUNTRY_WEIGHTS = np.array([3.0 if c == "United States" else 2.2 if c == "India" else 1.0 for c in COUNTRIES])
COUNTRY_WEIGHTS = COUNTRY_WEIGHTS / COUNTRY_WEIGHTS.sum()

# Pre-build the set of valid (Country, State, City) triples for validation.
VALID_GEO_TRIPLES = {
    (country, state, city)
    for country, info in COUNTRY_DATA.items()
    for city, state, _prefix, _area in info["cities"]
}


# ------------------------------------------------------------------ #
# Product catalog: realistic, recognizable product names with simple
# variants (storage/color/size) instead of generic templated names.
# ------------------------------------------------------------------ #
PRODUCT_CATALOG = {
    "Electronics": {
        "subs_variants": {"variant_type": "storage", "options": ["64GB", "128GB", "256GB", "512GB"], "step": 0.12},
        "items": [
            ("Apple iPhone 15", "Apple", "Smartphones", (799, 1199), (0.55, 0.65)),
            ("Samsung Galaxy S24", "Samsung", "Smartphones", (699, 1099), (0.55, 0.65)),
            ("Dell XPS 13 Laptop", "Dell", "Laptops", (899, 1599), (0.60, 0.70)),
            ("Apple MacBook Air", "Apple", "Laptops", (999, 1699), (0.55, 0.65)),
            ("Sony WH-1000XM5 Headphones", "Sony", "Headphones", (249, 399), (0.40, 0.55)),
            ("Apple AirPods Pro", "Apple", "Headphones", (199, 249), (0.40, 0.50)),
            ("Canon EOS R50 Camera", "Canon", "Cameras", (599, 999), (0.50, 0.60)),
            ("Apple Watch Series 9", "Apple", "Smartwatches", (399, 599), (0.45, 0.55)),
            ("Samsung Galaxy Tab S9", "Samsung", "Tablets", (599, 999), (0.50, 0.60)),
        ],
    },
    "Fashion": {
        "subs_variants": {"variant_type": "size_color", "options": ["S", "M", "L", "XL"], "step": 0.0},
        "items": [
            ("Nike Air Max 270", "Nike", "Shoes", (120, 180), (0.30, 0.40)),
            ("Adidas Ultraboost 22", "Adidas", "Shoes", (150, 190), (0.30, 0.40)),
            ("Levi's 501 Jeans", "Levi's", "Men's Clothing", (60, 100), (0.30, 0.40)),
            ("Zara Wool Coat", "Zara", "Women's Clothing", (80, 150), (0.30, 0.40)),
            ("Nike Dri-FIT T-Shirt", "Nike", "Men's Clothing", (25, 45), (0.30, 0.40)),
            ("Michael Kors Handbag", "Michael Kors", "Bags", (150, 350), (0.25, 0.35)),
            ("Ray-Ban Aviator Sunglasses", "Ray-Ban", "Accessories", (120, 180), (0.30, 0.40)),
        ],
    },
    "Home & Kitchen": {
        "subs_variants": {"variant_type": "color", "options": ["Black", "White", "Silver", "Red"], "step": 0.0},
        "items": [
            ("Instant Pot Duo 7-in-1", "Instant Pot", "Small Appliances", (60, 120), (0.40, 0.55)),
            ("Philips Air Fryer XXL", "Philips", "Small Appliances", (150, 250), (0.40, 0.55)),
            ("IKEA MALM Bed Frame", "IKEA", "Bedding", (150, 300), (0.40, 0.55)),
            ("Tefal Non-Stick Frying Pan Set", "Tefal", "Cookware", (30, 70), (0.35, 0.50)),
            ("Cuisinart Stand Mixer", "Cuisinart", "Small Appliances", (200, 400), (0.40, 0.55)),
        ],
    },
    "Beauty": {
        "subs_variants": {"variant_type": "size", "options": ["30ml", "50ml", "100ml"], "step": 0.10},
        "items": [
            ("L'Oreal Revitalift Serum", "L'Oreal", "Skincare", (12, 30), (0.20, 0.35)),
            ("Maybelline Fit Me Foundation", "Maybelline", "Makeup", (8, 18), (0.20, 0.35)),
            ("Nivea Soft Moisturizing Cream", "Nivea", "Skincare", (5, 12), (0.20, 0.35)),
            ("The Ordinary Niacinamide Serum", "The Ordinary", "Skincare", (6, 14), (0.20, 0.35)),
            ("Dove Shampoo & Conditioner", "Dove", "Haircare", (4, 10), (0.25, 0.40)),
        ],
    },
    "Sports": {
        "subs_variants": {"variant_type": "size_color", "options": ["S", "M", "L", "XL"], "step": 0.0},
        "items": [
            ("Nike Air Max 270", "Nike", "Shoes", (120, 180), (0.30, 0.40)),
            ("Wilson Evolution Basketball", "Wilson", "Team Sports", (30, 60), (0.40, 0.55)),
            ("Decathlon Yoga Mat", "Decathlon", "Fitness Equipment", (15, 40), (0.40, 0.55)),
            ("Yonex Badminton Racket", "Yonex", "Team Sports", (50, 120), (0.40, 0.55)),
            ("Under Armour Training Backpack", "Under Armour", "Outdoor Gear", (40, 80), (0.35, 0.50)),
        ],
    },
    "Books": {
        "subs_variants": None,
        "items": [
            ("Atomic Habits", "Penguin", "Non-Fiction", (12, 20), (0.45, 0.60)),
            ("The Hobbit", "HarperCollins", "Fiction", (10, 18), (0.45, 0.60)),
            ("Diary of a Wimpy Kid", "Scholastic", "Children", (8, 14), (0.45, 0.60)),
            ("Introduction to Algorithms", "Independent Press", "Academic", (40, 90), (0.45, 0.60)),
        ],
    },
    "Furniture": {
        "subs_variants": {"variant_type": "color", "options": ["Oak", "Walnut", "White", "Black"], "step": 0.0},
        "items": [
            ("IKEA KALLAX Shelf Unit", "IKEA", "Living Room", (60, 140), (0.45, 0.60)),
            ("Ashley Recliner Sofa", "Ashley", "Living Room", (400, 900), (0.45, 0.60)),
            ("Wayfair Basics Office Desk", "Wayfair Basics", "Office", (100, 250), (0.45, 0.60)),
            ("HomeCraft Outdoor Dining Set", "HomeCraft", "Outdoor", (200, 500), (0.45, 0.60)),
        ],
    },
    "Groceries": {
        "subs_variants": None,
        "items": [
            ("Nestle KitKat Multipack", "Nestle", "Snacks", (3, 6), (0.55, 0.70)),
            ("Kellogg's Corn Flakes", "Kellogg's", "Staples", (3, 7), (0.55, 0.70)),
            ("Lavazza Ground Coffee", "Unilever", "Beverages", (6, 14), (0.55, 0.70)),
            ("PepsiCo Lays Chips Family Pack", "PepsiCo", "Snacks", (3, 8), (0.55, 0.70)),
        ],
    },
    "Automotive": {
        "subs_variants": None,
        "items": [
            ("Bosch Wiper Blade Set", "Bosch", "Car Accessories", (15, 35), (0.50, 0.65)),
            ("Michelin All-Season Tyre", "Michelin", "Tyres & Wheels", (80, 180), (0.55, 0.70)),
            ("3M Car Wash & Wax Kit", "3M", "Tools", (20, 45), (0.45, 0.60)),
            ("Castrol GTX Engine Oil 5L", "Castrol", "Tools", (25, 55), (0.50, 0.65)),
        ],
    },
    "Jewelry": {
        "subs_variants": None,
        "items": [
            ("Pandora Moments Charm Bracelet", "Pandora", "Rings", (50, 120), (0.35, 0.50)),
            ("Swarovski Crystal Necklace", "Swarovski", "Necklaces", (80, 200), (0.35, 0.50)),
            ("Fossil Gen 6 Smartwatch", "Fossil", "Watches", (150, 300), (0.40, 0.55)),
        ],
    },
    "Pet Supplies": {
        "subs_variants": None,
        "items": [
            ("Pedigree Adult Dry Dog Food", "Pedigree", "Food", (15, 35), (0.45, 0.60)),
            ("Whiskas Cat Food Pouches", "Whiskas", "Food", (10, 25), (0.45, 0.60)),
            ("Kong Classic Dog Toy", "Kong", "Toys", (8, 18), (0.40, 0.55)),
        ],
    },
    "Baby Products": {
        "subs_variants": None,
        "items": [
            ("Pampers Baby Dry Diapers", "Pampers", "Diapers", (15, 30), (0.40, 0.55)),
            ("Huggies Little Movers Diapers", "Huggies", "Diapers", (15, 30), (0.40, 0.55)),
            ("Fisher-Price Rock-n-Play", "Fisher-Price", "Toys", (40, 90), (0.40, 0.55)),
        ],
    },
    "Office Supplies": {
        "subs_variants": None,
        "items": [
            ("HP DeskJet Printer", "HP", "Printers", (60, 150), (0.45, 0.60)),
            ("Staples Copy Paper Ream", "Staples", "Stationery", (5, 12), (0.45, 0.60)),
            ("Parker Jotter Ballpoint Pen Set", "Parker", "Stationery", (10, 25), (0.35, 0.50)),
        ],
    },
    "Garden": {
        "subs_variants": None,
        "items": [
            ("Fiskars Pruning Shears", "Fiskars", "Tools", (15, 35), (0.45, 0.60)),
            ("Weber Spirit Gas Grill", "Weber", "Grills", (300, 700), (0.45, 0.60)),
            ("Black+Decker Hedge Trimmer", "Black+Decker", "Tools", (40, 90), (0.45, 0.60)),
        ],
    },
    "Health": {
        "subs_variants": None,
        "items": [
            ("Centrum Multivitamin Tablets", "Centrum", "Vitamins", (10, 25), (0.35, 0.50)),
            ("Omron Blood Pressure Monitor", "Omron", "Medical Devices", (30, 70), (0.40, 0.55)),
            ("Fitbit Charge 6", "Fitbit", "Fitness Trackers", (100, 180), (0.40, 0.55)),
        ],
    },
}
CATEGORY_POPULARITY = {
    "Electronics": 1.6, "Fashion": 2.4, "Home & Kitchen": 1.5, "Beauty": 2.0,
    "Sports": 1.2, "Books": 1.1, "Furniture": 0.5, "Groceries": 2.2,
    "Automotive": 0.6, "Jewelry": 0.5, "Pet Supplies": 1.0, "Baby Products": 0.9,
    "Office Supplies": 0.8, "Garden": 0.6, "Health": 1.3,
}

PAYMENT_METHODS = ["Credit Card", "Debit Card", "PayPal", "Cash on Delivery", "Bank Transfer", "Digital Wallet"]
DELIVERY_METHODS = ["Standard", "Express", "Same-Day", "Pickup"]
SALES_CHANNELS = ["Website", "Mobile App", "Marketplace", "Social Commerce"]
DEVICE_TYPES = ["Mobile", "Desktop", "Tablet"]
TRAFFIC_SOURCES = ["Organic Search", "Paid Ads", "Social Media", "Email", "Direct", "Referral"]
WAREHOUSES = ["WH-EAST-01", "WH-WEST-01", "WH-CENTRAL-01", "WH-EU-01", "WH-APAC-01"]
RETURN_REASONS = ["Defective Product", "Wrong Item Shipped", "Size/Fit Issue", "No Longer Needed",
                   "Better Price Found Elsewhere", "Late Delivery", "Item Not as Described"]


def gen_ids(rng, prefix, n, length=10):
    """Deterministic, seeded pseudo-random IDs (NOT uuid4 -- keeps runs reproducible)."""
    chars = np.array(list("0123456789ABCDEF"))
    idx = rng.integers(0, len(chars), size=(n, length))
    return np.array([f"{prefix}-" + "".join(row) for row in chars[idx]])


def build_daily_weights(start_date, end_date):
    """Seasonal + year-over-year demand curve (Black Friday, Xmas, YoY growth, etc.)."""
    n_days = (end_date - start_date).days + 1
    w = np.ones(n_days)
    for i in range(n_days):
        d = start_date + timedelta(days=i)
        w[i] *= 1.0 + 0.28 * (d.year - start_date.year)          # YoY growth
        if d.weekday() in (5, 6):
            w[i] *= 1.15                                          # weekends
        bf = date(d.year, 11, 1)
        bf += timedelta(days=(3 - bf.weekday()) % 7 + 21 + 1)      # ~4th Fri + 1
        cm = bf + timedelta(days=3)
        if abs((d - bf).days) <= 1:
            w[i] *= 4.5
        elif d == cm:
            w[i] *= 3.8
        elif date(d.year, 12, 18) <= d <= date(d.year, 12, 24):
            w[i] *= 2.6
        elif d == date(d.year, 12, 25):
            w[i] *= 0.3
        elif date(d.year, 12, 26) <= d <= date(d.year, 12, 31):
            w[i] *= 1.8
        elif d == date(d.year, 1, 1):
            w[i] *= 1.3
        elif date(d.year, 2, 10) <= d <= date(d.year, 2, 14):
            w[i] *= 1.9
        elif date(d.year, 8, 15) <= d <= date(d.year, 9, 10):
            w[i] *= 1.6
    return w / w.sum()


# ------------------------------------------------------------------ #
# Customers -- built as a strict dependency chain, NOT independent draws:
#   Gender -> Name -> Country -> State -> City -> Postal_Code
#   -> Phone_Number -> Currency
# ------------------------------------------------------------------ #
def generate_customers(cfg: Config, rng: np.random.Generator) -> pd.DataFrame:
    n = cfg.n_customers
    logger.info(f"Generating {n:,} customers (relational attribute chain)...")

    genders = rng.choice(["Male", "Female"], size=n, p=[0.5, 0.5])
    countries = rng.choice(COUNTRIES, size=n, p=COUNTRY_WEIGHTS)
    segments = rng.choice(list(cfg.segment_probs.keys()), size=n, p=list(cfg.segment_probs.values()))
    ages = np.clip(rng.normal(34, 10, n), 16, 85).astype(int)

    span = (cfg.end_date - cfg.start_date).days
    reg_offsets = rng.integers(0, span + 1, size=n)
    reg_dates = np.array([cfg.start_date + timedelta(days=int(o)) for o in reg_offsets])

    names: List[str] = []
    states: List[str] = []
    cities: List[str] = []
    postal_codes: List[str] = []
    phones: List[str] = []
    currencies: List[str] = []
    emails: List[str] = []

    for i in range(n):
        gender = genders[i]
        country = countries[i]
        info = COUNTRY_DATA[country]

        # Name depends on gender (guarantees "Richard" -> Male, etc.) and
        # is drawn from the country's own name bank.
        first_pool = info["male_names"] if gender == "Male" else info["female_names"]
        first = rng.choice(first_pool)
        last = rng.choice(info["last_names"])
        name = f"{first} {last}"
        names.append(name)

        # City (and therefore State + postal prefix + phone area code) is
        # drawn from THIS country's own curated city list only.
        city, state, postal_prefix, phone_area = info["cities"][rng.integers(0, len(info["cities"]))]
        states.append(state)
        cities.append(city)
        postal_codes.append(info["postal_fn"](rng, postal_prefix))
        phones.append(info["phone_fn"](rng, phone_area))
        currencies.append(info["currency"])

        local = f"{first}.{last}".lower().replace(" ", "")
        domain = rng.choice(["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"])
        emails.append(f"{local}{rng.integers(1, 999)}@{domain}")

    df = pd.DataFrame({
        "Customer_ID": gen_ids(rng, "CUST", n, 10),
        "Customer_Name": names, "Gender": genders, "Age": ages,
        "Email": emails, "Phone_Number": phones, "Country": countries,
        "State": states, "City": cities, "Postal_Code": postal_codes,
        "Registration_Date": reg_dates, "Customer_Segment": segments,
        "Currency": currencies,
    })
    return df


# ------------------------------------------------------------------ #
# Products -- realistic named catalog + simple variants
# ------------------------------------------------------------------ #
def generate_products(cfg: Config, rng: np.random.Generator) -> pd.DataFrame:
    n = cfg.n_products
    logger.info(f"Generating {n:,} products from the realistic catalog...")

    categories = list(PRODUCT_CATALOG.keys())
    cat_w = np.array([CATEGORY_POPULARITY[c] for c in categories])
    cat_w = cat_w / cat_w.sum()
    chosen_categories = rng.choice(categories, size=n, p=cat_w)

    product_ids = gen_ids(rng, "PROD", n, 10)
    rows = []
    for i in range(n):
        cat = chosen_categories[i]
        spec = PRODUCT_CATALOG[cat]
        base_name, brand, sub_cat, price_range, cost_ratio_range = spec["items"][rng.integers(0, len(spec["items"]))]

        variant_spec = spec["subs_variants"]
        display_name = base_name
        price_multiplier = 1.0
        if variant_spec is not None:
            option = rng.choice(variant_spec["options"])
            step = variant_spec["step"]
            if variant_spec["variant_type"] == "storage":
                display_name = f"{base_name} ({option})"
                option_idx = variant_spec["options"].index(option)
                price_multiplier = 1.0 + option_idx * step
            elif variant_spec["variant_type"] == "size_color":
                display_name = f"{base_name} - Size {option}"
            else:  # plain size or color
                display_name = f"{base_name} ({option})"

        lo, hi = price_range
        base_price = np.exp(rng.uniform(np.log(lo), np.log(hi)))
        unit_price = float(np.round(base_price * price_multiplier, 2))

        cr_lo, cr_hi = cost_ratio_range
        cost_ratio = float(rng.uniform(cr_lo, cr_hi))

        popularity = CATEGORY_POPULARITY[cat] / (1.0 + (unit_price / max(hi, 1)) * 3.0)
        sku = f"SKU-{cat[:3].upper()}-{product_ids[i][-8:]}"

        rows.append((product_ids[i], sku, display_name, cat, sub_cat, brand, unit_price, cost_ratio, popularity))

    return pd.DataFrame(rows, columns=["Product_ID", "SKU", "Product_Name", "Category",
                                        "Sub_Category", "Brand", "Unit_Price",
                                        "Cost_Ratio", "Popularity_Weight"])


# ------------------------------------------------------------------ #
# Orders -- driven by real per-customer purchase history, not a flat
# random resample of the customer pool per row.
# ------------------------------------------------------------------ #
def _orders_per_customer(cfg: Config, rng: np.random.Generator, customers: pd.DataFrame) -> np.ndarray:
    """Compute how many orders each customer places, from their segment's
    annual order-rate range and how long they've been registered within
    the simulation window (their 'tenure')."""
    n = len(customers)
    reg_dates = customers["Registration_Date"].to_numpy()
    tenure_years = np.array([
        max((cfg.end_date - rd).days / 365.25, 0.05) for rd in reg_dates
    ])

    n_orders = np.zeros(n, dtype=int)
    for segment, (lo, hi) in cfg.segment_orders_per_year.items():
        mask = customers["Customer_Segment"].to_numpy() == segment
        idx = np.where(mask)[0]
        if len(idx) == 0:
            continue
        annual_rate = rng.uniform(lo, hi, size=len(idx))
        raw = np.round(annual_rate * tenure_years[idx]).astype(int)
        n_orders[idx] = np.clip(raw, 1, None)  # every customer has >= 1 order

    return n_orders


def generate_orders(cfg: Config, rng: np.random.Generator,
                     customers: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    n_cust, n_prod = len(customers), len(products)

    n_orders_per_cust = _orders_per_customer(cfg, rng, customers)
    total_orders = int(n_orders_per_cust.sum())
    logger.info(f"Simulated purchase history -> {total_orders:,} total order lines "
                f"across {n_cust:,} customers (avg {total_orders / n_cust:.1f} orders/customer).")

    # Expand each customer index according to their own order count, then
    # shuffle so rows aren't grouped by customer in the final table.
    cust_idx = np.repeat(np.arange(n_cust), n_orders_per_cust)
    rng.shuffle(cust_idx)
    m = len(cust_idx)

    cust = customers.iloc[cust_idx].reset_index(drop=True)

    # --- Product selection: VIP/Loyal customers skew towards pricier
    # items (on top of ordering more often), giving realistic spend
    # patterns rather than just higher order *counts*. ---
    base_w = products["Popularity_Weight"].to_numpy(float).copy()
    base_w /= base_w.sum()
    price = products["Unit_Price"].to_numpy(float)
    price_rank_boost = price / price.max()

    weights_by_segment = {}
    tilt = {"Regular": 0.0, "Loyal": 0.6, "VIP": 1.3}
    for seg, k in tilt.items():
        w = base_w * np.exp(k * price_rank_boost)
        weights_by_segment[seg] = w / w.sum()

    prod_idx = np.empty(m, dtype=int)
    seg_arr = cust["Customer_Segment"].to_numpy()
    for seg, w in weights_by_segment.items():
        mask = seg_arr == seg
        cnt = mask.sum()
        if cnt == 0:
            continue
        prod_idx[mask] = rng.choice(n_prod, size=cnt, p=w)

    prod = products.iloc[prod_idx].reset_index(drop=True)

    # --- Order date: seasonally weighted, but never before the
    # customer's own registration date. ---
    daily_w = build_daily_weights(cfg.start_date, cfg.end_date)
    n_days = len(daily_w)
    day_offsets = rng.choice(n_days, size=m, p=daily_w)
    order_dates = np.array([cfg.start_date + timedelta(days=int(o)) for o in day_offsets])
    reg_dates = cust["Registration_Date"].to_numpy()
    order_dates = np.array([max(o, r) for o, r in zip(order_dates, reg_dates)])

    quantity = rng.choice([1, 2, 3, 4, 5, 6, 8, 10], size=m,
                          p=[0.42, 0.26, 0.14, 0.08, 0.05, 0.03, 0.015, 0.005])
    discount_pct = rng.choice([0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40], size=m,
                              p=[0.50, 0.14, 0.14, 0.10, 0.07, 0.03, 0.02])

    unit_price = prod["Unit_Price"].to_numpy(float)
    cost_ratio = prod["Cost_Ratio"].to_numpy(float)
    gross = unit_price * quantity
    discount_amount = np.round(gross * discount_pct, 2)
    subtotal = np.round(gross - discount_amount, 2)

    countries = cust["Country"].to_numpy()
    tax_rate = np.array([COUNTRY_DATA[c]["tax"] for c in countries])
    tax = np.round(subtotal * tax_rate, 2)
    currency = cust["Currency"].to_numpy()

    delivery_method = rng.choice(DELIVERY_METHODS, size=m, p=[0.55, 0.28, 0.10, 0.07])
    base_ship = {"Standard": 4.0, "Express": 12.0, "Same-Day": 20.0, "Pickup": 0.0}
    shipping_cost = np.array([base_ship[d] for d in delivery_method])
    shipping_cost = np.round(np.clip(shipping_cost + rng.normal(0, 1, m), 0, None), 2)
    shipping_cost = np.where(subtotal >= 100, 0.0, shipping_cost)

    cost = np.round(unit_price * quantity * cost_ratio, 2)
    profit = np.round(subtotal - cost - shipping_cost, 2)
    total_amount = np.round(subtotal + tax + shipping_cost, 2)

    days_since = np.array([(cfg.end_date - d).days for d in order_dates])
    order_status = np.empty(m, dtype=object)
    recent = days_since <= 3
    transit = (days_since > 3) & (days_since <= 10)
    settled = days_since > 10
    if recent.any():
        order_status[recent] = rng.choice(["Processing", "Shipped"], recent.sum(), p=[0.65, 0.35])
    if transit.any():
        order_status[transit] = rng.choice(["Shipped", "Delivered", "Cancelled"], transit.sum(), p=[0.45, 0.45, 0.10])
    if settled.any():
        order_status[settled] = rng.choice(["Delivered", "Shipped", "Processing", "Cancelled", "Returned"],
                                            settled.sum(), p=[0.78, 0.03, 0.02, 0.07, 0.10])

    shipping_date = np.full(m, None, dtype=object)
    delivery_date = np.full(m, None, dtype=object)
    ships_or_beyond = np.isin(order_status, ["Shipped", "Delivered", "Returned"])
    ship_offset = rng.integers(0, 3, size=m)
    for i in np.where(ships_or_beyond)[0]:
        shipping_date[i] = order_dates[i] + timedelta(days=int(ship_offset[i]))
    delivered_or_returned = np.isin(order_status, ["Delivered", "Returned"])
    deliver_offset = rng.integers(1, 8, size=m)
    for i in np.where(delivered_or_returned)[0]:
        delivery_date[i] = shipping_date[i] + timedelta(days=int(deliver_offset[i]))

    is_returned = order_status == "Returned"
    return_reason = np.where(is_returned, rng.choice(RETURN_REASONS, size=m), None)
    refund_amount = np.where(is_returned, np.round(total_amount * rng.uniform(0.85, 1.0, m), 2), 0.0)
    returned_flag = np.where(is_returned, "Yes", "No")

    payment_status = np.empty(m, dtype=object)
    for status, mask in (("Cancelled", order_status == "Cancelled"), ("Returned", is_returned),
                         ("Processing", order_status == "Processing"),
                         ("Shipped", order_status == "Shipped"), ("Delivered", order_status == "Delivered")):
        idx = np.where(mask)[0]
        if len(idx) == 0:
            continue
        if status == "Cancelled":
            payment_status[idx] = rng.choice(["Cancelled", "Refunded"], len(idx), p=[0.8, 0.2])
        elif status == "Returned":
            payment_status[idx] = "Refunded"
        elif status == "Processing":
            payment_status[idx] = rng.choice(["Pending", "Paid"], len(idx), p=[0.6, 0.4])
        else:
            payment_status[idx] = rng.choice(["Paid", "Pending", "Failed"], len(idx), p=[0.94, 0.04, 0.02])

    rating = np.where(is_returned,
                       rng.choice([1, 2, 3, 4, 5], size=m, p=[0.20, 0.25, 0.25, 0.18, 0.12]),
                       rng.choice([1, 2, 3, 4, 5], size=m, p=[0.03, 0.05, 0.12, 0.35, 0.45]))
    review_count = rng.poisson(3.0, size=m)

    has_discount = discount_pct > 0
    coupon_pool = np.array(["SAVE10", "SAVE15", "SAVE20", "WELCOME10", "FESTIVE25",
                            "FREESHIP", "VIP30", "FLASH40", "BTS15", "NEWYEAR20"])
    coupon_code = np.where(has_discount & (rng.random(m) < 0.7), rng.choice(coupon_pool, size=m), None)

    n_sellers = max(50, n_prod // 20)
    seller_ids_pool = gen_ids(rng, "SELL", n_sellers, 8)
    seller_names_pool = np.array([f"Seller Co #{i+1}" for i in range(n_sellers)])
    sel = rng.integers(0, n_sellers, size=m)

    order_id = gen_ids(rng, "ORD", m, 12)
    session_id = gen_ids(rng, "SESS", m, 16)

    return pd.DataFrame({
        "Order_ID": order_id, "Customer_ID": cust["Customer_ID"].to_numpy(),
        "Customer_Name": cust["Customer_Name"].to_numpy(), "Gender": cust["Gender"].to_numpy(),
        "Age": cust["Age"].to_numpy(), "Email": cust["Email"].to_numpy(),
        "Phone_Number": cust["Phone_Number"].to_numpy(), "Country": countries,
        "State": cust["State"].to_numpy(), "City": cust["City"].to_numpy(),
        "Postal_Code": cust["Postal_Code"].to_numpy(), "Registration_Date": reg_dates,
        "Order_Date": order_dates, "Shipping_Date": shipping_date, "Delivery_Date": delivery_date,
        "Product_ID": prod["Product_ID"].to_numpy(), "SKU": prod["SKU"].to_numpy(),
        "Product_Name": prod["Product_Name"].to_numpy(), "Category": prod["Category"].to_numpy(),
        "Sub_Category": prod["Sub_Category"].to_numpy(), "Brand": prod["Brand"].to_numpy(),
        "Unit_Price": unit_price, "Quantity": quantity, "Discount_Percentage": discount_pct * 100,
        "Discount_Amount": discount_amount, "Tax": tax, "Shipping_Cost": shipping_cost,
        "Cost": cost, "Profit": profit, "Total_Amount": total_amount,
        "Payment_Method": rng.choice(PAYMENT_METHODS, size=m, p=[0.35, 0.20, 0.18, 0.10, 0.10, 0.07]),
        "Payment_Status": payment_status, "Order_Status": order_status,
        "Delivery_Method": delivery_method,
        "Warehouse": rng.choice(WAREHOUSES, size=m),
        "Seller_ID": seller_ids_pool[sel], "Seller_Name": seller_names_pool[sel],
        "Coupon_Code": coupon_code, "Returned": returned_flag, "Return_Reason": return_reason,
        "Refund_Amount": refund_amount, "Customer_Rating": rating, "Review_Count": review_count,
        "Customer_Segment": cust["Customer_Segment"].to_numpy(),
        "Device_Type": rng.choice(DEVICE_TYPES, size=m, p=[0.58, 0.35, 0.07]),
        "Traffic_Source": rng.choice(TRAFFIC_SOURCES, size=m, p=[0.28, 0.22, 0.20, 0.12, 0.13, 0.05]),
        "Session_ID": session_id, "Currency": currency,
        "Sales_Channel": rng.choice(SALES_CHANNELS, size=m, p=[0.45, 0.35, 0.15, 0.05]),
    })


# ------------------------------------------------------------------ #
# Validation (runs on the CLEAN data, before noise is injected)
# ------------------------------------------------------------------ #
def validate(df: pd.DataFrame) -> None:
    logger.info("Validating clean dataset...")
    assert df["Order_ID"].duplicated().sum() == 0, "Order_ID not unique"

    for col in ["Unit_Price", "Quantity", "Tax", "Shipping_Cost", "Cost", "Total_Amount"]:
        assert (df[col] >= 0).all(), f"Negative values in {col}"

    has_ship = df["Shipping_Date"].notna()
    assert not (has_ship & (df["Shipping_Date"] < df["Order_Date"])).any(), "Shipping before Order date"
    has_both = df["Shipping_Date"].notna() & df["Delivery_Date"].notna()
    assert not (has_both & (df["Delivery_Date"] < df["Shipping_Date"])).any(), "Delivery before Shipping date"
    assert not (df["Order_Date"] < df["Registration_Date"]).any(), "Order before Registration date"

    assert not ((df["Order_Status"] == "Cancelled") & df["Delivery_Date"].notna()).any(), "Cancelled has Delivery_Date"
    assert not ((df["Order_Status"] == "Processing") & df["Delivery_Date"].notna()).any(), "Processing has Delivery_Date"
    assert not ((df["Order_Status"] == "Processing") & df["Shipping_Date"].notna()).any(), "Processing has Shipping_Date"

    subtotal = df["Unit_Price"] * df["Quantity"] - df["Discount_Amount"]
    expected_total = np.round(subtotal + df["Tax"] + df["Shipping_Cost"], 2)
    assert ((df["Total_Amount"] - expected_total).abs() <= 0.05).all(), "Total_Amount mismatch"
    expected_profit = np.round(subtotal - df["Cost"] - df["Shipping_Cost"], 2)
    assert ((df["Profit"] - expected_profit).abs() <= 0.05).all(), "Profit mismatch"

    assert not ((df["Returned"] == "No") & (df["Refund_Amount"] > 0)).any(), "Non-returned order has refund"

    # --- New checks (this revision) ---
    # Geo-consistency: every (Country, State, City) triple must be one of
    # our known, real-world combinations -- catches any mixed-up geography.
    triples = set(zip(df["Country"], df["State"], df["City"]))
    bad_triples = triples - VALID_GEO_TRIPLES
    assert not bad_triples, f"Invalid Country/State/City combinations found: {bad_triples}"

    # Phone format sanity: no Faker-style extensions (e.g. "x1234").
    assert not df["Phone_Number"].str.contains("x", case=False, regex=False).any(), \
        "Phone_Number contains a Faker-style extension artifact"

    # Gender/name spot-check: every first name used must appear in the
    # matching gender's name bank for at least one country (defensive
    # check against future refactors breaking the gender->name chain).
    all_male = {nm for info in COUNTRY_DATA.values() for nm in info["male_names"]}
    all_female = {nm for info in COUNTRY_DATA.values() for nm in info["female_names"]}
    first_names = df["Customer_Name"].str.split().str[0]
    male_rows = df["Gender"] == "Male"
    female_rows = df["Gender"] == "Female"
    assert first_names[male_rows].isin(all_male).all(), "A 'Male' row has a non-male first name"
    assert first_names[female_rows].isin(all_female).all(), "A 'Female' row has a non-female first name"

    logger.info("All validation checks passed (incl. geo-consistency, phone format, gender/name match).")


# ------------------------------------------------------------------ #
# Data-quality noise injection
# ------------------------------------------------------------------ #
def inject_missing_values(df: pd.DataFrame, cfg: Config, rng: np.random.Generator) -> pd.DataFrame:
    df = df.copy()
    lo, hi = cfg.missing_value_pct_range
    eligible = [c for c in cfg.nullable_columns if c in df.columns]
    logger.info(f"Injecting missing values into {len(eligible)} columns...")
    n = len(df)
    for col in eligible:
        rate = rng.uniform(lo, hi)
        n_missing = int(n * rate)
        if n_missing == 0:
            continue
        idx = rng.choice(n, size=n_missing, replace=False)
        if pd.api.types.is_numeric_dtype(df[col]):
            df.loc[df.index[idx], col] = np.nan
        else:
            df.loc[df.index[idx], col] = None
    return df


def inject_duplicates(df: pd.DataFrame, cfg: Config, rng: np.random.Generator) -> pd.DataFrame:
    lo, hi = cfg.duplicate_pct_range
    rate = rng.uniform(lo, hi)
    n_dupes = int(len(df) * rate)
    logger.info(f"Injecting {n_dupes:,} duplicate rows ({rate*100:.1f}%)...")
    if n_dupes == 0:
        return df
    src = rng.choice(len(df), size=n_dupes, replace=True)
    dupes = df.iloc[src].copy().reset_index(drop=True)

    perturb = np.where(rng.random(n_dupes) < 0.5)[0]
    if len(perturb) > 0:
        choice = rng.integers(0, 3, size=len(perturb))
        r_idx = perturb[choice == 0]
        if len(r_idx) and "Customer_Rating" in dupes.columns:
            delta = rng.choice([-1, 1], size=len(r_idx))
            dupes.loc[r_idx, "Customer_Rating"] = np.clip(dupes.loc[r_idx, "Customer_Rating"].to_numpy() + delta, 1, 5)
        p_idx = perturb[choice == 1]
        if len(p_idx) and "Payment_Status" in dupes.columns:
            dupes.loc[p_idx, "Payment_Status"] = "Paid"
        v_idx = perturb[choice == 2]
        if len(v_idx) and "Review_Count" in dupes.columns:
            dupes.loc[v_idx, "Review_Count"] = dupes.loc[v_idx, "Review_Count"] + 1

    combined = pd.concat([df, dupes], ignore_index=True)
    combined = combined.sample(frac=1.0, random_state=int(rng.integers(0, 2**31 - 1))).reset_index(drop=True)
    return combined


# ------------------------------------------------------------------ #
# Export
# ------------------------------------------------------------------ #
def export(df: pd.DataFrame, cfg: Config) -> None:
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = cfg.output_basename
    for fmt in cfg.output_formats:
        fmt = fmt.lower().strip()
        path = out_dir / f"{base}.{fmt}"
        try:
            if fmt == "csv":
                df.to_csv(path, index=False)
            elif fmt == "parquet":
                df.to_parquet(path, index=False)
            elif fmt in ("xlsx", "excel"):
                df.to_excel(out_dir / f"{base}.xlsx", index=False, engine="openpyxl")
            else:
                logger.warning(f"Unknown format '{fmt}' skipped.")
                continue
            logger.info(f"Wrote {fmt.upper()}: {path}")
        except ImportError as e:
            logger.warning(f"Skipped {fmt.upper()} export -- missing dependency ({e}).")


# ------------------------------------------------------------------ #
# Main pipeline
# ------------------------------------------------------------------ #
def _estimate_n_customers(cfg: Config) -> int:
    """Roughly back out how many customers are needed to hit ~n_records,
    given the segment mix / annual-rate midpoints / average tenure."""
    span_years = (cfg.end_date - cfg.start_date).days / 365.25
    avg_tenure = span_years / 2.0  # registrations spread uniformly -> avg ~half the window
    avg_annual_rate = sum(
        cfg.segment_probs[seg] * sum(cfg.segment_orders_per_year[seg]) / 2.0
        for seg in cfg.segment_probs
    )
    avg_orders_per_customer = max(avg_annual_rate * avg_tenure, 1.0)
    return max(100, int(cfg.n_records / avg_orders_per_customer))


def main(cfg: Config = CONFIG) -> pd.DataFrame:
    random.seed(cfg.random_seed)
    np.random.seed(cfg.random_seed)
    rng = np.random.default_rng(cfg.random_seed)

    if not cfg.n_customers:
        cfg.n_customers = _estimate_n_customers(cfg)

    logger.info(f"Target ~{cfg.n_records:,} records -> using {cfg.n_customers:,} customers "
                f"(seed={cfg.random_seed})")

    customers = generate_customers(cfg, rng)
    products = generate_products(cfg, rng)
    orders = generate_orders(cfg, rng, customers, products)

    validate(orders)

    noisy = inject_missing_values(orders, cfg, rng)
    noisy = inject_duplicates(noisy, cfg, rng)

    export(noisy, cfg)
    logger.info(f"Done. Final shape: {noisy.shape[0]:,} rows x {noisy.shape[1]} columns.")
    return noisy


if __name__ == "__main__":
    main()