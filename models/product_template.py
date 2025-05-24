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