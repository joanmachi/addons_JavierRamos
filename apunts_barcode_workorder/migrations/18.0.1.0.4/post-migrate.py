# -*- coding: utf-8 -*-
def migrate(cr, version):
    # 18.0.1.0.4: introduccion del auto-producir + auto-back-order en la
    # ultima fase. No requiere cambios estructurales en datos existentes.
    # Si en el futuro hay que limpiar registros (p.ej. resetear un flag de
    # contexto persistente) se mete aqui.
    return
