"""
Static seed data: the three demo restaurants and their structured menus.

Kept separate from seed.py so the (long) product catalog does not clutter the
seeding logic. The `folder` field maps each restaurant to its knowledge-base
text files under data/<folder>/.
"""

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _hours(weekday_open, weekday_close, fri_sat_close=None, sun=None):
    """Build a Title-cased business-hours dict matching the frontend format."""
    hours = {}
    for day in _WEEKDAYS:
        if day == "Sunday" and sun is not None:
            hours[day] = {"open": sun[0], "close": sun[1], "closed": False}
        elif day in ("Friday", "Saturday") and fri_sat_close is not None:
            hours[day] = {"open": weekday_open, "close": fri_sat_close, "closed": False}
        else:
            hours[day] = {"open": weekday_open, "close": weekday_close, "closed": False}
    return hours


RESTAURANTS = [
    {
        "folder": "Restaurant_A",
        "name": "Pizza Paradise",
        "phone": "+91 120 4927200",
        "address": "Plot 15, Block K, Sector 18, Noida, Uttar Pradesh 201301, India",
        "description": "Gourmet Wood-Fired Pizzeria & Italian Bistro",
        "contact_email": "support@pizzaparadise.com",
        "delivery_notes": "We deliver within a 10 km radius across 3 zones. Free delivery over ₹499 (Zone 1).",
        "business_hours": _hours("11:00", "22:00", fri_sat_close="23:00", sun=("12:00", "21:00")),
        "cuisine": "Italian",
        "delivery_zones": [
            {"name": "Zone 1", "max_km": 3.0, "fee": 49, "free_over": 499, "eta_min": 40},
            {"name": "Zone 2", "max_km": 6.0, "fee": 79, "free_over": 699, "eta_min": 50},
            {"name": "Zone 3", "max_km": 10.0, "fee": 99, "free_over": 999, "eta_min": 60},
        ],
        "manager": {"email": "manager.pizza@icsa.com", "first": "Marco", "last": "Rossi"},
    },
    {
        "folder": "Restaurant_B",
        "name": "Burgers & Co",
        "phone": "+91 120 4955500",
        "address": "Plot 44, Block C, Sector 62, Noida, Uttar Pradesh 201309, India",
        "description": "Gourmet Smash Burgers & Craft Fries",
        "contact_email": "support@burgersandco.com",
        "delivery_notes": "Delivery available across Sector 62 and nearby. Hand-cut fries packed hot.",
        "business_hours": _hours("11:00", "23:00", fri_sat_close="23:59", sun=("12:00", "22:00")),
        "cuisine": "American",
        "delivery_zones": [
            {"name": "Zone 1", "max_km": 4.0, "fee": 39, "free_over": 399, "eta_min": 35},
            {"name": "Zone 2", "max_km": 8.0, "fee": 69, "free_over": 599, "eta_min": 50},
        ],
        "manager": {"email": "manager.burgers@icsa.com", "first": "Dana", "last": "Cole"},
    },
    {
        "folder": "Restaurant_C",
        "name": "Sushi Zen",
        "phone": "+91 120 4966600",
        "address": "Plot 88, Sector 15, Noida, Uttar Pradesh 201301, India",
        "description": "Premium Japanese Sushi & Ramen Bar",
        "contact_email": "support@sushizen.com",
        "delivery_notes": "Delivered in insulated boxes with cold packs to preserve freshness.",
        "business_hours": _hours("12:00", "22:30", fri_sat_close="23:00", sun=("12:00", "22:00")),
        "cuisine": "Japanese",
        "delivery_zones": [
            {"name": "Zone 1", "max_km": 3.0, "fee": 59, "free_over": 699, "eta_min": 45},
            {"name": "Zone 2", "max_km": 7.0, "fee": 99, "free_over": 999, "eta_min": 60},
        ],
        "manager": {"email": "manager.sushi@icsa.com", "first": "Kenji", "last": "Tanaka"},
    },
]


# Dietary tag shorthands
VEG = ["vegetarian"]
VEGAN = ["vegan"]
NONVEG = ["non-vegetarian"]
GF = "gluten-free"

_PIZZA_SIZES = lambda p, m, l: {"Personal 10\"": p, "Medium 12\"": m, "Large 16\"": l}

PRODUCTS = {
    "Restaurant_A": [
        {"name": "Margherita Royale", "category": "Vegetarian Pizzas", "base_price": 299, "size_prices": _PIZZA_SIZES(299, 499, 799), "dietary_tags": VEG, "allergens": ["Wheat/Gluten", "Milk"], "is_popular": True, "description": "San Marzano tomato, fresh mozzarella, basil on a 48-hour sourdough crust."},
        {"name": "Four Cheese Garden", "category": "Vegetarian Pizzas", "base_price": 349, "size_prices": _PIZZA_SIZES(349, 549, 849), "dietary_tags": VEG, "allergens": ["Wheat/Gluten", "Milk"], "description": "Mozzarella, gorgonzola, parmesan, ricotta, cherry tomatoes, spinach."},
        {"name": "Truffle Mushroom", "category": "Vegetarian Pizzas", "base_price": 399, "size_prices": _PIZZA_SIZES(399, 599, 899), "dietary_tags": VEG, "allergens": ["Wheat/Gluten", "Milk"], "description": "Wild mushrooms, white truffle oil, fontina cheese, rosemary."},
        {"name": "Vegan Garden Party", "category": "Vegan Pizzas", "base_price": 329, "size_prices": _PIZZA_SIZES(329, 529, 829), "dietary_tags": VEGAN, "allergens": ["Wheat/Gluten"], "description": "Vegan mozzarella, artichokes, roasted peppers, red onion, kalamata olives."},
        {"name": "Spicy Vegan Sausage", "category": "Vegan Pizzas", "base_price": 349, "size_prices": _PIZZA_SIZES(349, 549, 849), "dietary_tags": VEGAN, "allergens": ["Wheat/Gluten", "Soy"], "description": "Plant-based sausage crumbles, jalapeños, spicy marinara, arugula."},
        {"name": "Vegan Avocado Dream", "category": "Vegan Pizzas", "base_price": 399, "size_prices": _PIZZA_SIZES(399, 599, 899), "dietary_tags": VEGAN, "allergens": ["Wheat/Gluten"], "description": "Fresh avocado, cherry tomatoes, baby spinach, vegan garlic aioli."},
        {"name": "Ultimate Pepperoni Rush", "category": "Non-Vegetarian Pizzas", "base_price": 349, "size_prices": _PIZZA_SIZES(349, 549, 849), "dietary_tags": NONVEG, "allergens": ["Wheat/Gluten", "Milk"], "is_popular": True, "description": "Double pepperoni, fresh mozzarella, tomato sauce, oregano."},
        {"name": "Tuscan Meat Feast", "category": "Non-Vegetarian Pizzas", "base_price": 399, "size_prices": _PIZZA_SIZES(399, 649, 949), "dietary_tags": NONVEG, "allergens": ["Wheat/Gluten", "Milk"], "description": "Sausage, pepperoni, meatballs, ham, bacon, mozzarella, marinara."},
        {"name": "Chicken Pesto Bliss", "category": "Non-Vegetarian Pizzas", "base_price": 399, "size_prices": _PIZZA_SIZES(399, 599, 899), "dietary_tags": NONVEG, "allergens": ["Wheat/Gluten", "Milk", "Tree Nuts"], "description": "Grilled chicken, basil pesto, cherry & sun-dried tomatoes, pine nuts."},
        {"name": "Classic Fettuccine Alfredo", "category": "Pasta", "base_price": 299, "dietary_tags": VEG, "allergens": ["Wheat/Gluten", "Milk", "Eggs"], "description": "Fettuccine in a rich parmesan-butter cream sauce."},
        {"name": "Baked Beef Lasagna", "category": "Pasta", "base_price": 349, "dietary_tags": NONVEG, "allergens": ["Wheat/Gluten", "Milk", "Eggs"], "description": "Layered pasta, seasoned beef, ricotta, mozzarella, parmesan."},
        {"name": "Signature Tiramisu", "category": "Desserts", "base_price": 199, "dietary_tags": VEG, "allergens": ["Wheat/Gluten", "Milk", "Eggs"], "is_popular": True, "description": "Espresso-dipped ladyfingers, mascarpone cream, cocoa."},
        {"name": "Vegan Chocolate Decadence Cake", "category": "Desserts", "base_price": 219, "dietary_tags": VEGAN, "allergens": ["Wheat/Gluten", "Soy"], "description": "Double-chocolate vegan cake with strawberry glaze."},
        {"name": "Organic Lemonade", "category": "Beverages", "base_price": 89, "dietary_tags": VEGAN, "allergens": [], "description": "Hand-squeezed lemons, cane sugar, filtered water."},
    ],
    "Restaurant_B": [
        {"name": "Classic Smash Burger", "category": "Signature Beef Burgers", "base_price": 249, "size_prices": {"Single": 249, "Double": 349}, "dietary_tags": NONVEG, "allergens": ["Wheat/Gluten", "Milk"], "is_popular": True, "description": "Smashed beef patty, American cheese, pickles, lettuce, house sauce."},
        {"name": "Bacon Cheddar Crunch", "category": "Signature Beef Burgers", "base_price": 329, "size_prices": {"Single": 329, "Double": 429}, "dietary_tags": NONVEG, "allergens": ["Wheat/Gluten", "Milk"], "description": "Beef patty, bacon, sharp cheddar, crispy onions, BBQ sauce."},
        {"name": "Mushroom Swiss Truffle", "category": "Signature Beef Burgers", "base_price": 349, "size_prices": {"Single": 349, "Double": 449}, "dietary_tags": NONVEG, "allergens": ["Wheat/Gluten", "Milk"], "description": "Beef patty, Swiss, sautéed mushrooms, truffle garlic aioli."},
        {"name": "Crispy Buttermilk Chicken", "category": "Chicken Burgers", "base_price": 299, "dietary_tags": NONVEG, "allergens": ["Wheat/Gluten", "Milk"], "is_popular": True, "description": "Fried buttermilk chicken, spicy slaw, pickles, herb mayo."},
        {"name": "Grilled Pesto Chicken", "category": "Chicken Burgers", "base_price": 319, "dietary_tags": NONVEG, "allergens": ["Wheat/Gluten", "Milk"], "description": "Grilled chicken, mozzarella, rocket, sun-dried tomatoes, pesto aioli."},
        {"name": "Crunchy Veggie Delite", "category": "Vegetarian & Vegan Burgers", "base_price": 199, "dietary_tags": VEG, "allergens": ["Wheat/Gluten", "Milk"], "description": "Crispy vegetable-potato patty, cheese, tomato, onion, lettuce."},
        {"name": "Vegan BBQ Char", "category": "Vegetarian & Vegan Burgers", "base_price": 279, "dietary_tags": VEGAN + [GF], "allergens": [], "description": "Plant-based patty, vegan cheddar, pickles, BBQ sauce on a gluten-free bun."},
        {"name": "Hand-Cut Craft Fries", "category": "Sides & Shacks", "base_price": 99, "dietary_tags": VEG, "allergens": [], "is_popular": True, "description": "Sea-salted crispy russet fries."},
        {"name": "Beer-Battered Onion Rings", "category": "Sides & Shacks", "base_price": 129, "dietary_tags": VEG, "allergens": ["Wheat/Gluten"], "description": "Thick-cut onions in crispy beer batter with chipotle ranch."},
        {"name": "Thick Shakes", "category": "Beverages & Shakes", "base_price": 149, "dietary_tags": VEG, "allergens": ["Milk"], "description": "Hand-spun shakes: Double Chocolate, Vanilla, or Strawberry."},
    ],
    "Restaurant_C": [
        {"name": "Salmon Nigiri", "category": "Nigiri & Sashimi", "base_price": 299, "dietary_tags": NONVEG, "allergens": ["Fish"], "is_popular": True, "description": "Premium Norwegian salmon over seasoned sushi rice (2 pcs)."},
        {"name": "Tuna Nigiri", "category": "Nigiri & Sashimi", "base_price": 349, "dietary_tags": NONVEG, "allergens": ["Fish"], "description": "Fresh yellowfin tuna over seasoned sushi rice (2 pcs)."},
        {"name": "Ebi Shrimp Nigiri", "category": "Nigiri & Sashimi", "base_price": 279, "dietary_tags": NONVEG, "allergens": ["Shellfish"], "description": "Butterflied cooked tiger shrimp over sushi rice (2 pcs)."},
        {"name": "Spicy Tuna Roll", "category": "Sushi Rolls", "base_price": 499, "dietary_tags": NONVEG, "allergens": ["Fish", "Sesame"], "is_popular": True, "description": "Yellowfin tuna, spicy mayo, cucumber, sesame (8 pcs)."},
        {"name": "California Zen Roll", "category": "Sushi Rolls", "base_price": 449, "dietary_tags": NONVEG, "allergens": ["Shellfish", "Fish"], "description": "Snow crab, avocado, cucumber, orange tobiko (8 pcs)."},
        {"name": "Golden Dragon Roll", "category": "Sushi Rolls", "base_price": 799, "dietary_tags": NONVEG, "allergens": ["Shellfish", "Fish"], "description": "Shrimp tempura, eel, avocado, eel sauce, spicy mayo (8 pcs)."},
        {"name": "Zen Tonkotsu Ramen", "category": "Ramen", "base_price": 599, "dietary_tags": NONVEG, "allergens": ["Wheat/Gluten", "Eggs", "Soy"], "is_popular": True, "description": "18-hour pork broth, chashu pork, marinated egg, mushrooms, nori."},
        {"name": "Spicy Miso Ramen", "category": "Ramen", "base_price": 549, "dietary_tags": NONVEG, "allergens": ["Wheat/Gluten", "Eggs", "Soy"], "description": "Chicken-miso broth, minced chicken, egg, corn, chili threads."},
        {"name": "Vegan Shiitake Shoyu Ramen", "category": "Ramen", "base_price": 499, "dietary_tags": VEGAN, "allergens": ["Wheat/Gluten", "Soy"], "description": "Kelp & shiitake broth, tofu, bok choy, bamboo shoots."},
        {"name": "Salted Edamame", "category": "Starters & Sides", "base_price": 149, "dietary_tags": VEGAN, "allergens": ["Soy"], "description": "Steamed green soybeans with sea salt."},
        {"name": "Crispy Vegetable Tempura", "category": "Starters & Sides", "base_price": 249, "dietary_tags": VEG, "allergens": ["Wheat/Gluten"], "description": "Seasonal vegetables in a light tempura batter."},
        {"name": "Pork Gyoza", "category": "Starters & Sides", "base_price": 299, "dietary_tags": NONVEG, "allergens": ["Wheat/Gluten", "Soy"], "description": "Pan-seared pork dumplings with soy-vinegar dip (5 pcs)."},
    ],
}


# Human-readable titles + document types for the knowledge-base text files.
KB_FILES = {
    "restaurant_profile": ("Restaurant Profile", "restaurant_profile"),
    "menu": ("Menu", "menu"),
    "product_descriptions": ("Product Descriptions", "product_descriptions"),
    "modifiers": ("Modifiers & Customization", "modifiers"),
    "delivery_settings": ("Delivery Settings", "delivery_settings"),
    "delivery_policy": ("Delivery Policy", "delivery_policy"),
    "pickup_settings": ("Pickup Settings", "pickup_settings"),
    "faq": ("Frequently Asked Questions", "faq"),
    "refund_policy": ("Refund & Cancellation Policy", "refund_policy"),
    "business_rules": ("Business Rules & Protocols", "business_rules"),
}
