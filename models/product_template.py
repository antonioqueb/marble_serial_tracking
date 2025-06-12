# models/product_template.py
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Precios por metro cuadrado
    price_per_sqm_min = fields.Float(
        string='Precio Mínimo por m²',
        digits='Product Price',
        help='Precio mínimo de venta por metro cuadrado'
    )
    
    price_per_sqm_avg = fields.Float(
        string='Precio Promedio por m²',
        digits='Product Price',
        help='Precio promedio de venta por metro cuadrado'
    )
    
    price_per_sqm_max = fields.Float(
        string='Precio Máximo por m²',
        digits='Product Price',
        help='Precio máximo de venta por metro cuadrado'
    )

    # --- INICIO DEL CAMBIO ---
    # Añade este nuevo campo
    require_lot_selection_on_sale = fields.Boolean(
        string="Exigir Lote Específico en Venta",
        default=True,
        help="Si se marca, será obligatorio seleccionar un número de lote/serie en la orden de venta si hay stock disponible.\n"
             "Desmarcar para productos (como porcelanato) donde el lote se puede asignar durante el picking en el almacén."
    )
    # --- FIN DEL CAMBIO ---