with order_items as (
    select * from {{ ref('stg_order_items') }}
),

aggregated as (
    select
        order_id,
        count(order_item_id) as total_items,
        count(distinct product_id) as total_distinct_products,
        round(sum(price), 2) as total_items_amount,
        round(sum(freight_value), 2) as total_freight_amount,
        round(sum(price + freight_value), 2) as total_order_amount
    from order_items
    group by order_id
)

select * from aggregated
