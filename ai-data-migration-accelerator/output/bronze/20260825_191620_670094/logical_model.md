# Executive Summary

Logical design for datamodel, derived from the conceptual model. 20 entities carry 23 relationships: 2 associative entities resolve many-to-many relationships and 1 entities are identified through a parent. 0 entities required a surrogate identifier because no business key was recorded. Attributes are typed against abstract domains and carry no platform-specific length, precision or storage.

> Derived deterministically from `conceptual_model.json`. No AI was involved in this step: the conceptual model already carries the business judgement, and turning it into a normalized logical design is a set of transformation rules. Every design decision appears under Normalization or Assumptions.

# Logical Model Overview

- **Database:** datamodel
- **Subject areas:** 7
- **Entities:** 20 (17 fundamental, 1 dependent, 2 associative)
- **Attributes:** 78
- **Relationships:** 23 (5 identifying)
- **Normalization actions:** 15

# Subject Areas

## Geography

Master data for locations where customers, warehouses, and suppliers operate.

**Entities:** City, Country, State

## Organization

Internal company structure including employees, departments, and reporting relationships.

**Entities:** Department, Employee

## Product Master

Product catalog, categorization, supplier relationships, and inventory management.

**Entities:** Category, Inventory, Product, Product Promotion Association, Product Warehouse Association, Promotion, Supplier

## Sales

Customer information, order capture, order line items, and payment processing.

**Entities:** Customer, Order, Order Item, Payment

## Fulfillment

Shipment and return processing for orders.

**Entities:** Return Order, Shipment

## Audit & Compliance

System audit logging for tracking changes to data.

**Entities:** Audit Log

## Unassigned

Entities the conceptual model placed in no domain.

**Entities:** Warehouse

# Logical Entities

## Audit Log

System audit trail recording all data modifications for compliance and traceability.

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

Product categories used to classify and organize the product catalog (Accessories, Storage, etc.).

- **Kind:** Fundamental
- **Subject area:** Product Master
- **Primary key:** category_name
- **Derived from:** `bronze.category`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| category_name | Text | PK | Mandatory |  |

## City

Cities within states, the primary geographic unit for customer location and warehouse placement.

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

Sovereign nations and territories where the business operates or has customers and suppliers.

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

End customers who purchase products and place orders.

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

Organizational departments within the company (Finance, Support, etc.) that group employees.

- **Kind:** Fundamental
- **Subject area:** Organization
- **Primary key:** department_name
- **Derived from:** `bronze.department`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| department_name | Text | PK | Mandatory |  |

## Employee

Company staff members with role, compensation, and hierarchical reporting structure.

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

Stock levels of products held at specific warehouses, with reorder thresholds for supply chain management.

- **Kind:** Fundamental
- **Subject area:** Product Master
- **Primary key:** product_id, warehouse_id
- **Derived from:** `bronze.inventory`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| product_id | Text | PK | Mandatory |  |
| warehouse_id | Text | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| reorder_level | Text |  | Optional |  |
| Product sku | Identifier | FK | Mandatory | Product |
| warehouse_name | Identifier | FK | Mandatory | Warehouse |

## Order

Sales transactions placed by customers, managed by sales representatives and tracked through fulfillment.

- **Kind:** Fundamental
- **Subject area:** Sales
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

Individual line items within an order, specifying products, quantities, and unit prices.

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

Payment transactions received for orders, with method and date tracking.

- **Kind:** Fundamental
- **Subject area:** Sales
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

Goods sold and inventoried by the business, with pricing, supplier sourcing, and category classification.

- **Kind:** Fundamental
- **Subject area:** Product Master
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
- **Subject area:** Product Master
- **Primary key:** Product sku, promotion_name

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Product sku | Identifier | PK | Mandatory | Product |
| promotion_name | Identifier | PK | Mandatory | Promotion |

## Product Warehouse Association

Resolves the many-to-many relationship between Product and Warehouse. Each occurrence records that one Product references one Warehouse.

- **Kind:** Associative
- **Subject area:** Product Master
- **Primary key:** Product sku, warehouse_name

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Product sku | Identifier | PK | Mandatory | Product |
| warehouse_name | Identifier | PK | Mandatory | Warehouse |

## Promotion

Discount and promotional campaigns that can be applied to products.

- **Kind:** Fundamental
- **Subject area:** Product Master
- **Primary key:** promotion_name
- **Derived from:** `bronze.promotion`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| promotion_name | Text | PK | Mandatory |  |
| discount_percent | Text |  | Optional |  |

## Return Order

Product returns initiated by customers for orders, with reason tracking.

- **Kind:** Fundamental
- **Subject area:** Fulfillment
- **Primary key:** return_id
- **Derived from:** `bronze.return_order`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| return_id | Text | PK | Mandatory |  |
| return_reason | Text |  | Optional |  |
| Product sku | Identifier | FK | Optional | Product |
| order_id | Identifier | FK | Optional | Order |

## Shipment

Shipment records tracking the dispatch of orders from warehouses with tracking information.

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

States or provinces within countries used for geographic organization of customers and warehouses.

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

External vendors who supply products to the organization.

- **Kind:** Fundamental
- **Subject area:** Product Master
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

Physical distribution centers that hold inventory and ship orders to customers.

- **Kind:** Fundamental
- **Subject area:** Unassigned
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

**Confirmed Warehouse attributes are not repeated on Inventory.** Inventory references Warehouse, which references City. The chain is already decomposed, so City's attributes reach Inventory by navigation rather than by duplication.

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
