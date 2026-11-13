with orders as (
    select * from {{ ref('stg_orders') }}
),

items_summary as (
    select * from {{ ref('int_order_items_summary') }}
),

final as (
    select
        o.order_id,
        o.customer_id,
        o.order_status,
        o.order_purchase_at,
        o.order_approved_at,
        o.order_delivered_carrier_at,
        o.order_delivered_customer_at,
        o.order_estimated_delivery_at,
        
        -- Métricas de volume e financeiras
        coalesce(i.total_items, 0) as total_items,
        coalesce(i.total_distinct_products, 0) as total_distinct_products,
        coalesce(i.total_items_amount, 0.0) as total_items_amount,
        coalesce(i.total_freight_amount, 0.0) as total_freight_amount,
        coalesce(i.total_order_amount, 0.0) as total_order_amount,
        
        -- Lead time em dias corridos
        round(date_diff('hour', o.order_purchase_at, o.order_delivered_customer_at) / 24.0, 2) as delivery_time_days,
        
        -- Margem de entrega em relação à previsão (positivo = no prazo; negativo = atraso)
        round(date_diff('hour', o.order_delivered_customer_at, o.order_estimated_delivery_at) / 24.0, 2) as delivery_margin_days

    from orders o
    left join items_summary i on o.order_id = i.order_id
)

select * from final
