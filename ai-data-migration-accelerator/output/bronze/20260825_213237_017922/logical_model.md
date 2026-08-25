# Executive Summary

Logical design for datamodel, derived from the conceptual model. 20 entities carry 23 relationships: 2 associative entities resolve many-to-many relationships and 1 entities are identified through a parent. 0 entities required a surrogate identifier because no business key was recorded. Attributes are typed against abstract domains and carry no platform-specific length, precision or storage.

> Derived deterministically from `conceptual_model.json`. No AI was involved in this step: the conceptual model already carries the business judgement, and turning it into a normalized logical design is a set of transformation rules. Every design decision appears under Normalization or Assumptions.

# Logical Model Overview

- **Database:** datamodel
- **Subject areas:** 8
- **Entities:** 20 (17 fundamental, 1 dependent, 2 associative)
- **Attributes:** 78
- **Relationships:** 23 (5 identifying)
- **Normalization actions:** 15

# Subject Areas

## Geography

Reference data for locations: countries, states, cities, and warehouse locations.

**Entities:** City, Country, State, Warehouse

## Master Data

Core business reference entities: products, categories, suppliers, employees, departments, customers, and promotions.

**Entities:** Category, Customer, Department, Employee, Product, Product Promotion Association, Product Warehouse Association, Promotion, Supplier

## Inventory Management

Tracking product stock levels across warehouses and reorder thresholds.

**Entities:** Inventory

## Sales & Orders

Customer order creation, line items, order status, and sales representative assignment.

**Entities:** Order, Order Item

## Fulfillment

Shipment planning and execution from warehouses to customers.

**Entities:** Shipment

## Payments

Payment processing and tracking for customer orders.

**Entities:** Payment

## Returns

Product return processing and reason tracking.

**Entities:** Return Order

## Audit & Compliance

System audit logging for data change tracking and compliance.

**Entities:** Audit Log

# Logical Entities

## Audit Log

A system record of data modification operations for compliance and change tracking.

- **Kind:** Fundamental
- **Subject area:** Audit & Compliance
- **Primary key:** audit_id
- **Derived from:** `bronze.audit_log`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| audit_id | Text | PK | Mandatory |  |
| table_name | Text |  | Optional |  |
| operation | Code |  | Optional |  |
| user_name | Text |  | Optional |  |
| operation_timestamp | Text |  | Optional |  |

## Category

A product category used to classify and group products.

- **Kind:** Fundamental
- **Subject area:** Master Data
- **Primary key:** category_name
- **Derived from:** `bronze.category`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| category_name | Text | PK | Mandatory |  |

## City

A city located within a state.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** city_name, state_id
- **Derived from:** `bronze.city`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| city_name | Text | PK | Mandatory |  |
| state_id | Text | PK | Mandatory |  |
| state_name | Identifier | FK | Mandatory | State |

## Country

A sovereign nation or region where the business operates.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** country_code
- **Derived from:** `bronze.country`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| country_code | Text | PK | Mandatory |  |
| country_name | Text |  | Optional |  |
| created_at | Text |  | Optional |  |

## Customer

A person or organization that purchases products from the company.

- **Kind:** Fundamental
- **Subject area:** Master Data
- **Primary key:** customer_number
- **Alternate keys:** email
- **Derived from:** `bronze.customer`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| customer_number | Text | PK | Mandatory |  |
| first_name | Text |  | Optional |  |
| last_name | Text |  | Optional |  |
| email | Email | AK | Optional |  |
| phone | Phone |  | Optional |  |
| credit_limit | Text |  | Optional |  |
| status | Code |  | Optional |  |
| city_name | Identifier | FK | Optional | City |

## Department

An organizational unit within the company (Finance, Support, Sales, etc.).

- **Kind:** Fundamental
- **Subject area:** Master Data
- **Primary key:** department_name
- **Derived from:** `bronze.department`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| department_name | Text | PK | Mandatory |  |

## Employee

A staff member employed by the company, potentially in a sales, administrative, or management capacity.

- **Kind:** Fundamental
- **Subject area:** Master Data
- **Primary key:** email
- **Derived from:** `bronze.employee`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| email | Email | PK | Mandatory |  |
| first_name | Text |  | Optional |  |
| last_name | Text |  | Optional |  |
| salary | Amount |  | Optional |  |
| hire_date | Text |  | Optional |  |
| department_name | Identifier | FK | Optional | Department |
| Parent email | Identifier | FK | Optional | Employee |

## Inventory

The quantity of a specific product held at a specific warehouse, including reorder thresholds.

- **Kind:** Fundamental
- **Subject area:** Inventory Management
- **Primary key:** warehouse_id, product_id
- **Derived from:** `bronze.inventory`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| warehouse_id | Text | PK | Mandatory |  |
| product_id | Text | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| reorder_level | Text |  | Optional |  |
| warehouse_name | Identifier | FK | Mandatory | Warehouse |
| Product sku | Identifier | FK | Mandatory | Product |

## Order

A request from a customer to purchase one or more products, placed on a specific date with a status.

- **Kind:** Fundamental
- **Subject area:** Sales & Orders
- **Primary key:** order_id
- **Derived from:** `bronze.orders`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_id | Text | PK | Mandatory |  |
| order_date | Text |  | Optional |  |
| order_status | Text |  | Optional |  |
| Employee email | Identifier | FK | Optional | Employee |
| customer_number | Identifier | FK | Optional | Customer |

## Order Item

A line within an order specifying a product, quantity ordered, and unit price at time of order.

- **Kind:** Dependent
- **Subject area:** Sales & Orders
- **Primary key:** order_id, line_number
- **Derived from:** `bronze.order_item`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_id | Text | PK | Mandatory | Order |
| line_number | Text | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| unit_price | Text |  | Optional |  |
| Product sku | Identifier | FK | Optional | Product |

## Payment

A monetary transaction settling all or part of an order, including method and date.

- **Kind:** Fundamental
- **Subject area:** Payments
- **Primary key:** payment_id
- **Derived from:** `bronze.payment`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| payment_id | Text | PK | Mandatory |  |
| payment_method | Text |  | Optional |  |
| payment_date | Text |  | Optional |  |
| amount | Amount |  | Optional |  |
| order_id | Identifier | FK | Optional | Order |

## Product

A tangible good offered for sale or held in inventory.

- **Kind:** Fundamental
- **Subject area:** Master Data
- **Primary key:** sku
- **Derived from:** `bronze.product`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| sku | Code | PK | Mandatory |  |
| product_name | Text |  | Optional |  |
| unit_price | Text |  | Optional |  |
| status | Code |  | Optional |  |
| category_name | Identifier | FK | Optional | Category |
| supplier_name | Identifier | FK | Optional | Supplier |

## Product Promotion Association

Resolves the many-to-many relationship between Product and Promotion. Each occurrence records that one Product references one Promotion.

- **Kind:** Associative
- **Subject area:** Master Data
- **Primary key:** Product sku, promotion_name

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Product sku | Identifier | PK | Mandatory | Product |
| promotion_name | Identifier | PK | Mandatory | Promotion |

## Product Warehouse Association

Resolves the many-to-many relationship between Product and Warehouse. Each occurrence records that one Product references one Warehouse.

- **Kind:** Associative
- **Subject area:** Master Data
- **Primary key:** Product sku, warehouse_name

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Product sku | Identifier | PK | Mandatory | Product |
| warehouse_name | Identifier | PK | Mandatory | Warehouse |

## Promotion

A marketing campaign or discount offer applied to products.

- **Kind:** Fundamental
- **Subject area:** Master Data
- **Primary key:** promotion_name
- **Derived from:** `bronze.promotion`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| promotion_name | Text | PK | Mandatory |  |
| discount_percent | Text |  | Optional |  |

## Return Order

A request to return a product from an order, with reason for return.

- **Kind:** Fundamental
- **Subject area:** Returns
- **Primary key:** return_id
- **Derived from:** `bronze.return_order`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| return_id | Text | PK | Mandatory |  |
| return_reason | Text |  | Optional |  |
| Product sku | Identifier | FK | Optional | Product |
| order_id | Identifier | FK | Optional | Order |

## Shipment

The fulfillment of an order from a warehouse, with tracking information and ship date.

- **Kind:** Fundamental
- **Subject area:** Fulfillment
- **Primary key:** tracking_number
- **Derived from:** `bronze.shipment`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| tracking_number | Text | PK | Mandatory |  |
| shipped_date | Text |  | Optional |  |
| warehouse_name | Identifier | FK | Optional | Warehouse |
| order_id | Identifier | FK | Optional | Order |

## State

A state or province within a country.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** state_name, country_id
- **Derived from:** `bronze.state`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| state_name | Text | PK | Mandatory |  |
| country_id | Text | PK | Mandatory |  |
| country_code | Identifier | FK | Mandatory | Country |

## Supplier

A vendor that supplies products to the company.

- **Kind:** Fundamental
- **Subject area:** Master Data
- **Primary key:** supplier_name
- **Alternate keys:** email
- **Derived from:** `bronze.supplier`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| supplier_name | Text | PK | Mandatory |  |
| contact_name | Text |  | Optional |  |
| email | Email | AK | Optional |  |
| phone | Phone |  | Optional |  |

## Warehouse

A distribution facility storing inventory and fulfilling shipments.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** warehouse_name
- **Derived from:** `bronze.warehouse`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| warehouse_name | Text | PK | Mandatory |  |
| city_name | Identifier | FK | Optional | City |

# Entity Relationships

| Parent | Child | Cardinality | Optionality | Identifying | Foreign key |
|---|---|---|---|---|---|
| Category | Product | one-to-many | Optional | No | category_name |
| City | Customer | one-to-many | Optional | No | city_name |
| City | Warehouse | one-to-many | Optional | No | city_name |
| Country | State | one-to-many | Mandatory | No | country_code |
| Customer | Order | one-to-many | Optional | No | customer_number |
| Department | Employee | one-to-many | Optional | No | department_name |
| Employee | Employee | one-to-many | Optional | No | Parent email |
| Employee | Order | one-to-many | Optional | No | Employee email |
| Order | Order Item | one-to-many | Mandatory | Yes | order_id |
| Order | Payment | one-to-many | Optional | No | order_id |
| Order | Return Order | one-to-many | Optional | No | order_id |
| Order | Shipment | one-to-many | Optional | No | order_id |
| Product | Inventory | one-to-many | Mandatory | No | Product sku |
| Product | Order Item | one-to-many | Optional | No | Product sku |
| Product | Product Promotion Association | one-to-many | Mandatory | Yes | Product sku |
| Product | Product Warehouse Association | one-to-many | Mandatory | Yes | Product sku |
| Product | Return Order | one-to-many | Optional | No | Product sku |
| Promotion | Product Promotion Association | one-to-many | Mandatory | Yes | promotion_name |
| State | City | one-to-many | Mandatory | No | state_name |
| Supplier | Product | one-to-many | Optional | No | supplier_name |
| Warehouse | Inventory | one-to-many | Mandatory | No | warehouse_name |
| Warehouse | Product Warehouse Association | one-to-many | Mandatory | Yes | warehouse_name |
| Warehouse | Shipment | one-to-many | Optional | No | warehouse_name |

# Normalization

Actions taken and checks performed while deriving the logical design. Checks that found nothing are listed too, so a compliant design is distinguishable from one that was never examined.

### 1NF — Product Promotion Association

**Resolved many-to-many between Product and Promotion.** A many-to-many relationship cannot be represented without a repeating group. An associative entity keyed on both parents removes the repetition and gives the relationship a place to carry its own attributes later.

### 1NF — Product Warehouse Association

**Resolved many-to-many between Product and Warehouse.** A many-to-many relationship cannot be represented without a repeating group. An associative entity keyed on both parents removes the repetition and gives the relationship a place to carry its own attributes later.

### 2NF — Inventory

**Checked non-key attributes against the full composite key.** Inventory has a composite key, so every non-key attribute (quantity, reorder_level) must depend on the whole key rather than part of it. No partial dependency was found.

### 2NF — Order Item

**Checked non-key attributes against the full composite key.** Order Item has a composite key, so every non-key attribute (quantity, unit_price) must depend on the whole key rather than part of it. No partial dependency was found.

### 2NF — Order Item

**Identified Order Item as dependent on Order.** Its business key includes Order's key (order_id), so it cannot be identified independently. The relationship is identifying and the key is propagated rather than duplicated.

### 3NF — City

**Confirmed State attributes are not repeated on City.** City references State, which references Country. The chain is already decomposed, so Country's attributes reach City by navigation rather than by duplication.

### 3NF — Customer

**Confirmed City attributes are not repeated on Customer.** Customer references City, which references State. The chain is already decomposed, so State's attributes reach Customer by navigation rather than by duplication.

### 3NF — Inventory

**Confirmed Product attributes are not repeated on Inventory.** Inventory references Product, which references Supplier. The chain is already decomposed, so Supplier's attributes reach Inventory by navigation rather than by duplication.

### 3NF — Order

**Confirmed Customer attributes are not repeated on Order.** Order references Customer, which references City. The chain is already decomposed, so City's attributes reach Order by navigation rather than by duplication.

### 3NF — Order Item

**Confirmed Order attributes are not repeated on Order Item.** Order Item references Order, which references Customer. The chain is already decomposed, so Customer's attributes reach Order Item by navigation rather than by duplication.

### 3NF — Payment

**Confirmed Order attributes are not repeated on Payment.** Payment references Order, which references Customer. The chain is already decomposed, so Customer's attributes reach Payment by navigation rather than by duplication.

### 3NF — Product Warehouse Association

**Confirmed Warehouse attributes are not repeated on Product Warehouse Association.** Product Warehouse Association references Warehouse, which references City. The chain is already decomposed, so City's attributes reach Product Warehouse Association by navigation rather than by duplication.

### 3NF — Return Order

**Confirmed Order attributes are not repeated on Return Order.** Return Order references Order, which references Customer. The chain is already decomposed, so Customer's attributes reach Return Order by navigation rather than by duplication.

### 3NF — Shipment

**Confirmed Order attributes are not repeated on Shipment.** Shipment references Order, which references Customer. The chain is already decomposed, so Customer's attributes reach Shipment by navigation rather than by duplication.

### 3NF — Warehouse

**Confirmed City attributes are not repeated on Warehouse.** Warehouse references City, which references State. The chain is already decomposed, so State's attributes reach Warehouse by navigation rather than by duplication.

# Assumptions

_None identified._
