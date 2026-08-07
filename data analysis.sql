# Create big table to insert the overall data into database from csv

CREATE TABLE ecommerce_raw (
    order_id VARCHAR(50),
    customer_id VARCHAR(50),
    customer_name VARCHAR(100),
    gender VARCHAR(20),
    age INT,
    email VARCHAR(100),
    phone_number VARCHAR(30),
    country VARCHAR(50),
    state VARCHAR(50),
    city VARCHAR(50),
    postal_code VARCHAR(20),
    registration_date DATE,
    order_date DATE,
    shipping_date DATE,
    delivery_date DATE,
    product_id VARCHAR(50),
    sku VARCHAR(50),
    product_name VARCHAR(100),
    category VARCHAR(50),
    sub_category VARCHAR(50),
    brand VARCHAR(50),
    unit_price DECIMAL(10,2),
    quantity INT,
    discount_percentage DECIMAL(5,2),
    discount_amount DECIMAL(10,2),
    tax DECIMAL(10,2),
    shipping_cost DECIMAL(10,2),
    cost DECIMAL(10,2),
    profit DECIMAL(10,2),
    total_amount DECIMAL(10,2),
    payment_method VARCHAR(50),
    payment_status VARCHAR(50),
    order_status VARCHAR(50),
    delivery_method VARCHAR(50),
    warehouse VARCHAR(50),
    seller_id VARCHAR(50),
    seller_name VARCHAR(100),
    coupon_code VARCHAR(50),
    returned VARCHAR(20),
    return_reason VARCHAR(100),
    refund_amount DECIMAL(10,2),
    customer_rating DECIMAL(2,1),
    review_count INT,
    customer_segment VARCHAR(50),
    device_type VARCHAR(50),
    traffic_source VARCHAR(50),
    session_id VARCHAR(100),
    currency VARCHAR(10),
    sales_channel VARCHAR(50)
);

# Verify that the data inserted properly

SELECT 
    COUNT(*)
FROM
    ecommerce_raw;

SELECT 
    *
FROM
    ecommerce_raw
LIMIT 5;

# ================ Normalize the database =================== #

# Create locations table

CREATE TABLE locations (
    location_id INT PRIMARY KEY AUTO_INCREMENT,
    country VARCHAR(50),
    state VARCHAR(50),
    city VARCHAR(50),
    postal_code VARCHAR(50)
);

# Create categories table

CREATE TABLE categories (
    category_id INT PRIMARY KEY AUTO_INCREMENT,
    category VARCHAR(50),
    sub_category VARCHAR(50)
);

# Create brand table

CREATE TABLE brands (
    brand_id INT PRIMARY KEY AUTO_INCREMENT,
    brand VARCHAR(50)
);

# Create seller table

CREATE TABLE sellers (
    seller_id VARCHAR(50) PRIMARY KEY,
    seller_name VARCHAR(50)
);

# Create warehouse table

CREATE TABLE warehouses (
    warehouse_id INT PRIMARY KEY AUTO_INCREMENT,
    warehouse_name VARCHAR(100)
);

# Create customers table    
    
CREATE TABLE customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    location_id INT,
    customer_name VARCHAR(50) NOT NULL,
    gender VARCHAR(50),
    age INT CHECK (age > 0 AND age < 150),
    email VARCHAR(50) UNIQUE,
    phone_number VARCHAR(50) UNIQUE,
    registration_date DATETIME,
    customer_segment VARCHAR(50),
    FOREIGN KEY (location_id)
        REFERENCES locations (location_id)
);

# Create table products

CREATE TABLE products (
    product_id VARCHAR(50) PRIMARY KEY,
    category_id INT,
    brand_id INT,
    product_name VARCHAR(100),
    sku VARCHAR(50),
    FOREIGN KEY (category_id)
        REFERENCES categories (category_id),
    FOREIGN KEY (brand_id)
        REFERENCES brands (brand_id)
);

# Create sessions table

CREATE TABLE sessions (
    session_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50),
    device_type VARCHAR(50),
    traffic_source VARCHAR(50),
    sales_channel VARCHAR(50),
    FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id)
);

# create orders table

CREATE TABLE orders (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50),
    warehouse_id INT,
    session_id VARCHAR(50),
    order_date DATE,
    shipping_date DATE,
    delivery_date DATE,
    order_status VARCHAR(50),
    delivery_method VARCHAR(50),
    FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id),
    FOREIGN KEY (warehouse_id)
        REFERENCES warehouses (warehouse_id),
    FOREIGN KEY (session_id)
        REFERENCES sessions (session_id)
);

# Create order_items table

CREATE TABLE order_items (
    order_item_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id VARCHAR(50),
    product_id VARCHAR(50),
    seller_id VARCHAR(50),
    unit_price FLOAT CHECK (unit_price > 0),
    quantity INT CHECK (quantity > 0),
    discount_percentage FLOAT,
    discount_amount FLOAT,
    tax FLOAT,
    shipping_cost FLOAT,
    cost FLOAT,
    total_amount FLOAT CHECK (total_amount > 0),
    FOREIGN KEY (order_id)
        REFERENCES orders (order_id),
    FOREIGN KEY (product_id)
        REFERENCES products (product_id),
    FOREIGN KEY (seller_id)
        REFERENCES sellers (seller_id)
);

# Create payments table

CREATE TABLE payments (
    payment_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id VARCHAR(50),
    payment_method VARCHAR(50),
    payment_status VARCHAR(50),
    currency VARCHAR(50),
    FOREIGN KEY (order_id)
        REFERENCES orders (order_id)
);

# create returns table

CREATE TABLE returns (
    return_id INT PRIMARY KEY AUTO_INCREMENT,
    order_item_id INT,
    returned VARCHAR(50),
    return_reason VARCHAR(100),
    refund_amount FLOAT,
    FOREIGN KEY (order_item_id)
        REFERENCES order_items (order_item_id)
);

# Create reviews table

CREATE TABLE reviews (
    review_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id VARCHAR(50),
    product_id VARCHAR(50),
    customer_rating FLOAT,
    FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id),
    FOREIGN KEY (product_id)
        REFERENCES products (product_id)
);
    
# =========== Insert data to normalized database =============== #

# Insert data into locations table

insert into locations(country,state,city,postal_code) 
SELECT DISTINCT
    country, state, city, postal_code
FROM
    ecommerce_raw;
    
# Insert data into categories table

insert into categories(category,sub_category)

SELECT DISTINCT
    category, sub_category
FROM
    ecommerce_raw;
    
# Insert data into brand table
    
insert into brands(brand)

SELECT DISTINCT
    brand
FROM
    ecommerce_raw;

 # Insert data into sellers table 
 
 insert into  sellers(seller_id,seller_name)
 
SELECT DISTINCT
    seller_id, seller_name
FROM
    ecommerce_raw;
    
# insert data into warehoueses table

insert into warehouses(warehouse_name)

SELECT DISTINCT
    warehouse
FROM
    ecommerce_raw;
    
# Insert data into customers table

INSERT INTO customers
(
    customer_id,
    location_id,
    customer_name,
    gender,
    age,
    email,
    phone_number,
    registration_date,
    customer_segment
)
SELECT
    er.customer_id,
    MAX(l.location_id),
    MAX(er.customer_name),
    MAX(er.gender),
    MAX(er.age),
    MAX(er.email),
    MAX(er.phone_number),
    MAX(er.registration_date),
    MAX(er.customer_segment)
FROM ecommerce_raw er
JOIN locations l
    ON er.country = l.country
   AND er.state = l.state
   AND er.city = l.city
   AND (
        er.postal_code = l.postal_code
        OR (er.postal_code IS NULL AND l.postal_code IS NULL)
   )
GROUP BY er.customer_id;

# Insert data into products table 

INSERT INTO products
(
    product_id,
    category_id,
    brand_id,
    product_name,
    sku
)

SELECT
    er.product_id,
    c.category_id,
    b.brand_id,
    er.product_name,
    er.sku

FROM ecommerce_raw AS er

JOIN categories AS c
ON er.category = c.category
AND er.sub_category = c.sub_category

JOIN brands AS b
ON er.brand = b.brand

GROUP BY
    er.product_id,
    c.category_id,
    b.brand_id,
    er.product_name,
    er.sku;

# Insert data into session table

INSERT INTO sessions
(
    session_id,
    customer_id,
    device_type,
    traffic_source,
    sales_channel
)
SELECT
    session_id,
    customer_id,
    MAX(device_type),
    MAX(traffic_source),
    MAX(sales_channel)
FROM ecommerce_raw
GROUP BY
    session_id,
    customer_id;

# Insert data into orders table

SELECT
    order_id,
    COUNT(*) AS total
FROM ecommerce_raw
GROUP BY order_id
HAVING COUNT(*) > 1;

# Insert data to orders table

INSERT INTO orders (
    order_id,
    customer_id,
    warehouse_id,
    session_id,
    order_date,
    shipping_date,
    delivery_date,
    order_status,
    delivery_method
)
SELECT
    er.order_id,
    MAX(er.customer_id),
    MAX(w.warehouse_id),
    MAX(er.session_id),
    MAX(er.order_date),
    MAX(er.shipping_date),
    MAX(er.delivery_date),
    MAX(er.order_status),
    MAX(er.delivery_method)
FROM ecommerce_raw er
JOIN warehouses w
    ON er.warehouse = w.warehouse_name
GROUP BY er.order_id;

# Insert data into order_items table

INSERT INTO order_items (
    order_id,
    product_id,
    seller_id,
    unit_price,
    quantity,
    discount_percentage,
    discount_amount,
    tax,
    shipping_cost,
    cost,
    total_amount
)
SELECT
    order_id,
    product_id,
    seller_id,
    unit_price,
    quantity,
    discount_percentage,
    discount_amount,
    tax,
    shipping_cost,
    cost,
    total_amount
FROM ecommerce_raw;

# Insert data to payment table

INSERT INTO payments (
    order_id,
    payment_method,
    payment_status,
    currency
)
SELECT
    order_id,
    MAX(payment_method) AS payment_method,
    MAX(payment_status) AS payment_status,
    MAX(currency) AS currency
FROM ecommerce_raw
GROUP BY order_id;

# Insert into Return table

INSERT INTO returns (
    order_item_id,
    returned,
    return_reason,
    refund_amount
)
SELECT
    oi.order_item_id,
    er.returned,
    er.return_reason,
    er.refund_amount
FROM ecommerce_raw er
JOIN order_items oi
    ON er.order_id = oi.order_id
    AND er.product_id = oi.product_id
    AND er.seller_id = oi.seller_id
WHERE er.returned = 'Yes';

# Insert data into reviews table

INSERT INTO reviews (
    customer_id,
    product_id,
    customer_rating
)
SELECT DISTINCT
    er.customer_id,
    er.product_id,
    er.customer_rating
FROM ecommerce_raw er
WHERE er.customer_rating IS NOT NULL;

# =================== Data Analysis ===================== #

# Overall Sales and Profitability Analysis

-- What is the total revenue generated?

SELECT 
    SUM(total_amount) AS total_revenue
FROM
    order_items;
    
-- What is the total profit generated?

SELECT 
    SUM(profit) AS total_profit
FROM
    order_items;

-- What is the overall profit margin?

SELECT 
    (SUM(profit) / SUM(total_amount)) * 100 AS profit_margin
FROM
    order_items;

-- How many total orders have been placed?

SELECT 
    COUNT(*)
FROM
    orders
WHERE
    order_status = 'Delivered';
    
-- How many unique customers have purchased?

SELECT 
    COUNT(*) AS total_customers
FROM
    customers;

-- What is the average order value?

SELECT 
    (SUM(oi.total_amount) / COUNT(DISTINCT o.order_id)) AS avg_order_value
FROM
    orders o
        JOIN
    order_items oi ON o.order_id = oi.order_id;

-- What is the average profit per order?

SELECT 
    (SUM(oi.profit) / COUNT(DISTINCT o.order_id)) AS averge_profit
FROM
    orders o
        JOIN
    order_items oi ON o.order_id = oi.order_id;
    
-- How does revenue trend change over time?

SELECT 
    YEAR(o.order_date) AS years,
    MONTH(o.order_date) AS months,
    SUM(oi.total_amount) AS total_revenue
FROM
    orders o
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY years , months
ORDER BY years , months;

# How does profit trend change over time?

SELECT 
    YEAR(o.order_date) AS years,
    MONTH(o.order_date) AS months,
    SUM(oi.profit) AS total_profit
FROM
    orders o
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY years , months
ORDER BY years , months;

-- Are there periods where revenue increased but profit declined?

WITH monthly_sales AS (
    SELECT
        YEAR(o.order_date) AS order_year,
        MONTH(o.order_date) AS order_month,
        SUM(oi.total_amount) AS revenue,
        SUM(oi.profit) AS profit
    FROM orders o
    JOIN order_items oi
        ON o.order_id = oi.order_id
    GROUP BY order_year, order_month
)

SELECT
    order_year,
    order_month,
    revenue,
     LAG(revenue) OVER(ORDER BY order_year, order_month) AS previous_revenue,
    profit,
    LAG(profit) OVER(ORDER BY order_year, order_month) AS previous_profit
FROM monthly_sales; 

# Product and Category Profitability Analysis

-- Which categories generate the highest revenue?

SELECT 
    c.category, SUM(oi.total_amount) AS revenue
FROM
    categories c
        JOIN
    products p ON c.category_id = p.category_id
        JOIN
    order_items oi ON p.product_id = oi.product_id
GROUP BY c.category
ORDER BY revenue DESC;

-- Which categories generate the highest profit?

SELECT 
    c.category, SUM(oi.profit) AS total_profit
FROM
    categories c
        JOIN
    products p ON c.category_id = p.category_id
        JOIN
    order_items oi ON p.product_id = oi.product_id
GROUP BY c.category
ORDER BY total_profit DESC;

-- What is the profit margin by category?

SELECT 
    c.category,
    ((SUM(oi.profit) / SUM(oi.total_amount)) * 100) AS profit_margin
FROM
    categories c
        JOIN
    products p ON c.category_id = p.category_id
        JOIN
    order_items oi ON p.product_id = oi.product_id
GROUP BY c.category
ORDER BY profit_margin DESC;

-- Which products generate the highest sales?

SELECT 
    p.product_name, SUM(oi.total_amount) AS total_sales
FROM
    products p
        JOIN
    order_items oi ON p.product_id = oi.product_id
GROUP BY product_name
ORDER BY total_sales DESC;

-- Which products generate the highest profit?

SELECT 
    product_name, SUM(profit) AS total_profit
FROM
    products p
        JOIN
    order_items oi ON p.product_id = oi.product_id
GROUP BY product_name
ORDER BY total_profit DESC;

 -- Which products have high revenue but low profitability?
 
 with product_avg  as
 (
	SELECT 
    (SUM(oi.total_amount) / COUNT(DISTINCT p.product_id)) AS avg_revenue,
    (SUM(oi.profit) / COUNT(DISTINCT p.product_id)) AS avg_profit
FROM
    products p
        JOIN
    order_items oi ON p.product_id = oi.product_id
 
 )
 
SELECT 
    p.product_name,
    SUM(oi.total_amount) AS revenue,
    SUM(oi.profit) AS profit
FROM
    products p
        JOIN
    order_items oi ON p.product_id = oi.product_id
GROUP BY p.product_name
HAVING revenue > (SELECT 
        avg_revenue
    FROM
        product_avg)
    AND profit < (SELECT 
        avg_profit
    FROM
        product_avg);

-- Which products generate negative profit?

SELECT 
    p.product_name, SUM(oi.profit) AS profit
FROM
    products p
        JOIN
    order_items oi ON p.product_id = oi.product_id
GROUP BY product_name
HAVING SUM(oi.profit) < 0;

-- Which categories contribute the most to total company profit?

SELECT 
    c.category, SUM(oi.profit) AS total_profit
FROM
    categories c
        JOIN
    products p ON c.category_id = p.category_id
        JOIN
    order_items oi ON p.product_id = oi.product_id
GROUP BY c.category
ORDER BY total_profit DESC;

-- Which products or categories should be promoted or reviewed?

SELECT 
    p.product_name AS product,
    SUM(oi.total_amount) AS revenue,
    SUM(oi.profit) AS total_profit,
    ((SUM(oi.profit) / SUM(oi.total_amount)) * 100) AS profit_margin
FROM
    products p
        JOIN
    order_items oi ON p.product_id = oi.product_id
GROUP BY p.product_name
ORDER BY profit_margin desc;

# Customer Profitability Analysis

-- How many unique customers are there?

SELECT 
    COUNT(*) AS unique_customers
FROM
    customers;

-- Which customers generate the highest revenue?

SELECT 
    c.customer_name, SUM(oi.total_amount) AS revenue
FROM
    customers c
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY c.customer_name
ORDER BY revenue DESC;

-- Which customers generate the highest profit?

SELECT 
    c.customer_name, SUM(oi.profit) AS profit
FROM
    customers c
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY c.customer_name
ORDER BY profit DESC;

-- Are high-spending customers also high-profit customers?

WITH customer_summary AS (

    SELECT
        c.customer_id,
        c.customer_name,
        SUM(oi.total_amount) AS revenue,
        SUM(oi.profit) AS profit

    FROM customers c
    JOIN orders o
        ON c.customer_id = o.customer_id
    JOIN order_items oi
        ON o.order_id = oi.order_id

    GROUP BY
        c.customer_id,
        c.customer_name

)

, customer_average AS (

    SELECT
        AVG(revenue) AS avg_revenue,
        AVG(profit) AS avg_profit

    FROM customer_summary

)

SELECT
    cs.customer_name,
    cs.revenue,
    cs.profit

FROM customer_summary cs

CROSS JOIN customer_average ca

WHERE cs.revenue > ca.avg_revenue
AND cs.profit > ca.avg_profit;

-- Which customers generate high revenue but low profit? 

with avg_revenue as (

	SELECT 
    (SUM(oi.profit) / COUNT(distinct c.customer_id)) AS avg_profit,
    (SUM(oi.total_amount) / COUNT( distinct c.customer_id)) AS avg_revenue
FROM
    customers c
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id

)

SELECT 
    c.customer_name,
    SUM(oi.total_amount) AS revenue,
    SUM(oi.profit) AS profit
FROM
    customers c
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY c.customer_name
HAVING SUM(oi.total_amount) > (SELECT 
        avg_revenue
    FROM
        avg_revenue)
    AND SUM(oi.profit) < (SELECT 
        avg_profit
    FROM
        avg_revenue);

-- What is the average customer spending?

SELECT 
    (SUM(oi.total_amount) / COUNT(distinct c.customer_id)) AS avg_spending
FROM
    customers c
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id;


-- Which customer groups contribute the most profit?

SELECT 
    c.customer_segment, SUM(oi.profit) AS profit
FROM
    customers c
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY c.customer_segment
ORDER BY profit DESC;

# Sales Channel Performance Analysis.

-- Which sales channels generate the highest revenue?

SELECT 
    s.sales_channel, SUM(oi.total_amount) AS revenue
FROM
    sessions s
        JOIN
    orders o ON s.session_id = o.session_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY s.sales_channel
ORDER BY revenue DESC;
    
-- Which sales channels generate the highest profit?

SELECT 
    s.sales_channel, SUM(oi.profit) AS profit
FROM
    sessions s
        JOIN
    orders o ON s.session_id = o.session_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY s.sales_channel
ORDER BY profit DESC;

-- What is the profit margin by sales channel?

SELECT 
    s.sales_channel,
    ROUND((SUM(oi.profit) / NULLIF(SUM(oi.total_amount), 0)) * 100,
            2) AS profit_margin
FROM
    sessions s
        JOIN
    orders o ON s.session_id = o.session_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY s.sales_channel
ORDER BY profit_margin DESC;

-- Which channels have high sales but low profitability?

with channels as (
	
    SELECT 
    (sum(oi.profit) / COUNT(DISTINCT s.sales_channel)) AS avg_profit,
    (sum(oi.total_amount) / COUNT(DISTINCT s.sales_channel)) AS avg_revenue
FROM
    sessions s
        JOIN
    orders o ON s.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id

) 

SELECT 
    s.sales_channel,
    SUM(oi.profit) AS profit,
    SUM(oi.total_amount) AS revenue
FROM
    sessions s
        JOIN
    orders o ON s.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY s.sales_channel
HAVING SUM(oi.total_amount) > (SELECT 
        avg_revenue
    FROM
        channels)
    AND SUM(oi.profit) < (SELECT 
        avg_profit
    FROM
        channels);

-- Which channels receive the highest discounts?

SELECT 
    s.sales_channel, SUM(oi.discount_amount) AS discount
FROM
    sessions s
        JOIN
    orders o ON s.session_id = o.session_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY s.sales_channel
ORDER BY discount DESC;

-- Which sales channel provides the best balance between revenue and profit?

SELECT
    s.sales_channel,
    SUM(oi.total_amount) AS total_revenue,
    SUM(oi.profit) AS total_profit,
    ROUND(
        (SUM(oi.profit) / NULLIF(SUM(oi.total_amount), 0)) * 100,
        2
    ) AS profit_margin
FROM sessions s
JOIN orders o
    ON s.session_id = o.session_id
JOIN order_items oi
    ON o.order_id = oi.order_id
GROUP BY s.sales_channel
ORDER BY total_revenue DESC, total_profit DESC;

# countries Performance Analysis

-- Which country generate the highest revenue?

SELECT 
    l.country, SUM(oi.total_amount) AS revenue
FROM
    locations l
        JOIN
    customers c ON l.location_id = c.location_id
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY l.country
ORDER BY revenue DESC;

-- Which country generate the highest profit?

SELECT 
    l.country, SUM(oi.profit) AS profit
FROM
    locations l
        JOIN
    customers c ON l.location_id = c.location_id
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY l.country
ORDER BY profit DESC;

-- What is the profit margin by country?

SELECT 
    l.country, ((SUM(oi.profit) / sum(oi.total_amount)) * 100 ) AS profit_margin
FROM
    locations l
        JOIN
    customers c ON l.location_id = c.location_id
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY l.country
ORDER BY profit_margin DESC;

-- Which country have high sales but low profitability?

with countries_avg as (
SELECT 
    (SUM(oi.total_amount) / COUNT(DISTINCT l.country)) AS avg_revenue,
    (SUM(oi.profit) / COUNT(DISTINCT l.country)) AS avg_profit
FROM
    locations l
        JOIN
    customers c ON l.location_id = c.location_id
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
    
    )
    
SELECT 
    l.country,
    SUM(oi.total_amount) AS revenue,
    SUM(oi.profit) AS profit
FROM
    locations l
        JOIN
    customers c ON l.location_id = c.location_id
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY l.country
HAVING revenue > (SELECT 
        avg_revenue
    FROM
        countries_avg)
    AND profit < (SELECT 
        avg_profit
    FROM
        countries_avg);
    

-- Which country are negatively impacting profit?

SELECT 
    l.country, SUM(oi.profit) AS profit
FROM
    locations l
        JOIN
    customers c ON l.location_id = c.location_id
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY l.country
HAVING SUM(oi.profit) < 0;

-- Which Country represent growth opportunities?

SELECT 
    l.country,
    SUM(oi.total_amount) AS revenue,
    SUM(oi.profit) AS profit
FROM
    locations l
        JOIN
    customers c ON l.location_id = c.location_id
        JOIN
    orders o ON c.customer_id = o.customer_id
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY l.country
ORDER BY revenue;

# Discount Impact Analysis

-- What is the average discount percentage?

SELECT AVG(discount_percentage) AS average_discount
FROM order_items;

-- How does discount percentage affect profit?

SELECT
    CASE
        WHEN oi.discount_percentage = 0 THEN 'No Discount'
        WHEN oi.discount_percentage <= 10 THEN '1-10%'
        WHEN oi.discount_percentage <= 20 THEN '11-20%'
        WHEN oi.discount_percentage <= 30 THEN '21-30%'
        ELSE 'Above 30%'
    END AS discount_segment,

    COUNT(DISTINCT o.order_id) AS total_orders,

    SUM(oi.total_amount) AS total_revenue,

    SUM(oi.profit) AS total_profit,

    ROUND((SUM(oi.profit) / SUM(oi.total_amount)) * 100, 2) AS profit_margin

FROM orders o
JOIN order_items oi
    ON o.order_id = oi.order_id

GROUP BY discount_segment

ORDER BY
CASE
    WHEN discount_segment = 'No Discount' THEN 1
    WHEN discount_segment = '1-10%' THEN 2
    WHEN discount_segment = '11-20%' THEN 3
    WHEN discount_segment = '21-30%' THEN 4
    ELSE 5
END;


-- Which products receive the highest discounts?

SELECT 
    p.product_name, SUM(oi.discount_amount) AS discount
FROM
    products p
        JOIN
    order_items oi ON p.product_id = oi.product_id
GROUP BY p.product_name
ORDER BY discount DESC;

-- Which categories receive the highest discounts?

SELECT 
    c.category, SUM(oi.discount_amount) AS discount
FROM
    categories c
        JOIN
    products p ON c.category_id = p.category_id
        JOIN
    order_items oi ON p.product_id = oi.product_id
GROUP BY c.category
ORDER BY discount DESC;

-- Which discount levels provide the best profitability?

SELECT 
    CASE
        WHEN oi.discount_percentage = 0 THEN 'No Discount'
        WHEN oi.discount_percentage <= 10 THEN '1-10%'
        WHEN oi.discount_percentage <= 20 THEN '11-20%'
        WHEN oi.discount_percentage <= 30 THEN '21-30%'
        ELSE 'Above 30%'
    END AS discount_segment,
    SUM(oi.profit) AS total_profit,
    ROUND((SUM(oi.profit) / SUM(oi.total_amount)) * 100,
            2) AS profit_margin
FROM
    orders o
        JOIN
    order_items oi ON o.order_id = oi.order_id
GROUP BY discount_segment
ORDER BY CASE
    WHEN discount_segment = 'No Discount' THEN 1
    WHEN discount_segment = '1-10%' THEN 2
    WHEN discount_segment = '11-20%' THEN 3
    WHEN discount_segment = '21-30%' THEN 4
    ELSE 5
END;

