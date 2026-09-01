# Executive Summary

Logical design for datamodel, derived from the conceptual model. 20 entities carry 23 relationships: 2 associative entities resolve many-to-many relationships and 1 entities are identified through a parent. 0 entities required a surrogate identifier because no business key was recorded. Attributes are typed against abstract domains and carry no platform-specific length, precision or storage.

> Derived deterministically from `conceptual_model.json`. No AI was involved in this step: the conceptual model already carries the business judgement, and turning it into a normalized logical design is a set of transformation rules. Every design decision appears under Normalization or Assumptions.

# Logical Model Overview

- **Database:** datamodel
- **Subject areas:** 7
- **Entities:** 20 (17 fundamental, 1 dependent, 2 associative)
- **Attributes:** 77
- **Relationships:** 23 (5 identifying)
- **Normalization actions:** 16

# Subject Areas

## Geography

Master data for countries, states, cities, and warehouse locations that serve as reference points across the enterprise.

**Entities:** City, Country, State, Warehouse

## Catalog

Product master data including categorization, suppliers, pricing, and promotional campaigns.

**Entities:** Category, Product, Product Promotion Association, Product Warehouse Association, Promotion, Supplier

## Sales

Customer master data, sales orders, order items, and sales representative management.

**Entities:** Customer, Order, Order Item

## Fulfillment

Warehouse inventory management, order shipments, and product returns processing.

**Entities:** Inventory, Return, Shipment

## Finance

Payment processing and financial transaction recording for customer orders.

**Entities:** Payment

## Organization

Employee master data, department structure, and management hierarchies.

**Entities:** Department, Employee

## Operations

System audit and operational logging of database changes.

**Entities:** Audit Log

# Logical Entities

## Audit Log

System-generated record of all database operations (INSERT, UPDATE, DELETE) with timestamp and user information for compliance and troubleshooting.

- **Kind:** Fundamental
- **Subject area:** Operations
- **Primary key:** operation_timestamp, table_name, user_name
- **Derived from:** `bronze.audit_log`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| operation_timestamp | Text | PK | Mandatory |  |
| table_name | Text | PK | Mandatory |  |
| user_name | Text | PK | Mandatory |  |
| operation | Code |  | Optional |  |

## Category

Product classification scheme that organizes the product catalog into logical groupings (e.g., Accessories, Storage).

- **Kind:** Fundamental
- **Subject area:** Catalog
- **Primary key:** category_name
- **Derived from:** `bronze.category`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| category_name | Text | PK | Mandatory |  |

## City

City location record that belongs to a state, used for customer addresses and warehouse locations.

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

Sovereign nation reference with ISO country code, serving as the top level of geographic hierarchy.

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

Individual or organization that places orders. Identified by a customer number and has a credit limit and active status.

- **Kind:** Fundamental
- **Subject area:** Sales
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

Organizational unit to which employees are assigned, representing teams or functions such as Finance or Support.

- **Kind:** Fundamental
- **Subject area:** Organization
- **Primary key:** department_name
- **Derived from:** `bronze.department`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| department_name | Text | PK | Mandatory |  |

## Employee

Person employed by the company who may be a sales representative, manager, or other operational role. Employees report to managers within a hierarchy.

- **Kind:** Fundamental
- **Subject area:** Organization
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

Stock position of a product at a specific warehouse, including current quantity on hand and reorder trigger level. This is a managed entity tracking supply.

- **Kind:** Fundamental
- **Subject area:** Fulfillment
- **Primary key:** warehouse_id, product_id
- **Derived from:** `bronze.inventory`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| warehouse_id | Text | PK | Mandatory |  |
| product_id | Text | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| reorder_level | Text |  | Optional |  |
| Product sku | Identifier | FK | Mandatory | Product |
| warehouse_name | Identifier | FK | Mandatory | Warehouse |

## Order

Customer purchase order placed on a specific date, assigned to a sales representative, with a fulfillment status (e.g., DELIVERED).

- **Kind:** Fundamental
- **Subject area:** Sales
- **Primary key:** order_id
- **Derived from:** `bronze.orders`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_id | Text | PK | Mandatory |  |
| order_date | Text |  | Optional |  |
| order_status | Text |  | Optional |  |
| customer_number | Identifier | FK | Optional | Customer |
| Employee email | Identifier | FK | Optional | Employee |

## Order Item

Line item within an order specifying the product, quantity ordered, and unit price at time of sale.

- **Kind:** Dependent
- **Subject area:** Sales
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

Financial transaction recording customer payment against an order, including method (e.g., UPI), date, and amount.

- **Kind:** Fundamental
- **Subject area:** Finance
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

Saleable item in the catalog, identified by SKU, with a category, supplier, unit price, and active status.

- **Kind:** Fundamental
- **Subject area:** Catalog
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
- **Subject area:** Catalog
- **Primary key:** Product sku, promotion_name

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Product sku | Identifier | PK | Mandatory | Product |
| promotion_name | Identifier | PK | Mandatory | Promotion |

## Product Warehouse Association

Resolves the many-to-many relationship between Product and Warehouse. Each occurrence records that one Product references one Warehouse.

- **Kind:** Associative
- **Subject area:** Catalog
- **Primary key:** Product sku, warehouse_name

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Product sku | Identifier | PK | Mandatory | Product |
| warehouse_name | Identifier | PK | Mandatory | Warehouse |

## Promotion

Marketing campaign offering a discount percentage that can apply to one or more products.

- **Kind:** Fundamental
- **Subject area:** Catalog
- **Primary key:** promotion_name
- **Derived from:** `bronze.promotion`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| promotion_name | Text | PK | Mandatory |  |
| discount_percent | Text |  | Optional |  |

## Return

Record of a product being returned from an order, including the reason (e.g., Damaged).

- **Kind:** Fundamental
- **Subject area:** Fulfillment
- **Primary key:** return_id
- **Derived from:** `bronze.return_order`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| return_id | Text | PK | Mandatory |  |
| return_reason | Text |  | Optional |  |
| order_id | Identifier | FK | Optional | Order |
| Product sku | Identifier | FK | Optional | Product |

## Shipment

Outbound movement of order fulfillment from a warehouse, with tracking number and shipment date.

- **Kind:** Fundamental
- **Subject area:** Fulfillment
- **Primary key:** tracking_number
- **Derived from:** `bronze.shipment`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| tracking_number | Text | PK | Mandatory |  |
| shipped_date | Text |  | Optional |  |
| order_id | Identifier | FK | Optional | Order |
| warehouse_name | Identifier | FK | Optional | Warehouse |

## State

Geographic subdivision of a country, used to organize cities and define regional hierarchies.

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

Vendor organization that supplies products to the company, with contact details.

- **Kind:** Fundamental
- **Subject area:** Catalog
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

Physical location where inventory is stored and orders are fulfilled, situated in a city.

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
| Order | Return | one-to-many | Optional | No | order_id |
| Order | Shipment | one-to-many | Optional | No | order_id |
| Product | Inventory | one-to-many | Mandatory | No | Product sku |
| Product | Order Item | one-to-many | Optional | No | Product sku |
| Product | Product Promotion Association | one-to-many | Mandatory | Yes | Product sku |
| Product | Product Warehouse Association | one-to-many | Mandatory | Yes | Product sku |
| Product | Return | one-to-many | Optional | No | Product sku |
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

### 2NF — Audit Log

**Checked non-key attributes against the full composite key.** Audit Log has a composite key, so every non-key attribute (operation) must depend on the whole key rather than part of it. No partial dependency was found.

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

**Confirmed Warehouse attributes are not repeated on Inventory.** Inventory references Warehouse, which references City. The chain is already decomposed, so City's attributes reach Inventory by navigation rather than by duplication.

### 3NF — Order

**Confirmed Employee attributes are not repeated on Order.** Order references Employee, which references Employee. The chain is already decomposed, so Employee's attributes reach Order by navigation rather than by duplication.

### 3NF — Order Item

**Confirmed Product attributes are not repeated on Order Item.** Order Item references Product, which references Supplier. The chain is already decomposed, so Supplier's attributes reach Order Item by navigation rather than by duplication.

### 3NF — Payment

**Confirmed Order attributes are not repeated on Payment.** Payment references Order, which references Employee. The chain is already decomposed, so Employee's attributes reach Payment by navigation rather than by duplication.

### 3NF — Product Warehouse Association

**Confirmed Warehouse attributes are not repeated on Product Warehouse Association.** Product Warehouse Association references Warehouse, which references City. The chain is already decomposed, so City's attributes reach Product Warehouse Association by navigation rather than by duplication.

### 3NF — Return

**Confirmed Product attributes are not repeated on Return.** Return references Product, which references Supplier. The chain is already decomposed, so Supplier's attributes reach Return by navigation rather than by duplication.

### 3NF — Shipment

**Confirmed Warehouse attributes are not repeated on Shipment.** Shipment references Warehouse, which references City. The chain is already decomposed, so City's attributes reach Shipment by navigation rather than by duplication.

### 3NF — Warehouse

**Confirmed City attributes are not repeated on Warehouse.** Warehouse references City, which references State. The chain is already decomposed, so State's attributes reach Warehouse by navigation rather than by duplication.

# Assumptions

_None identified._
