from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.purchase_order import PurchaseOrder
from app.models.material import Material


def get_purchase_orders_by_material(db: Session, material_code: str):
    return db.query(PurchaseOrder).filter(PurchaseOrder.material_code == material_code).order_by(PurchaseOrder.year.desc(), PurchaseOrder.month.desc()).all()


def get_purchase_order(db: Session, po_id: int):
    return db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()


def get_purchase_order_by_number(db: Session, po_number: str):
    return db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_number).first()


def create_purchase_order(db: Session, po_data):
    material = db.query(Material).filter(Material.material_code == po_data.material_code).first()
    if not material:
        return None, f"Material '{po_data.material_code}' not found"

    existing = get_purchase_order_by_number(db, po_data.po_number)
    if existing:
        return None, "Purchase order already exists"

    if po_data.receive_qty is not None and po_data.order_qty is not None and po_data.receive_qty > po_data.order_qty:
        return None, "receive_qty cannot be greater than order_qty"

    po = PurchaseOrder(
        material_code=po_data.material_code,
        po_number=po_data.po_number,
        order_qty=po_data.order_qty,
        receive_qty=po_data.receive_qty,
        year=po_data.year,
        month=po_data.month,
    )
    db.add(po)
    try:
        db.commit()
        db.refresh(po)
    except IntegrityError:
        db.rollback()
        return None, "Purchase order already exists"

    return po, None


def update_purchase_order(db: Session, po_id: int, po_data):
    po = get_purchase_order(db, po_id)
    if not po:
        return None, "Purchase order not found"

    if po_data.po_number and po_data.po_number != po.po_number:
        existing = get_purchase_order_by_number(db, po_data.po_number)
        if existing:
            return None, "Purchase order already exists"
        po.po_number = po_data.po_number

    if po_data.order_qty is not None:
        po.order_qty = po_data.order_qty
    if po_data.receive_qty is not None:
        po.receive_qty = po_data.receive_qty
    if po_data.year is not None:
        po.year = po_data.year
    if po_data.month is not None:
        po.month = po_data.month

    if po.receive_qty is not None and po.order_qty is not None and po.receive_qty > po.order_qty:
        return None, "receive_qty cannot be greater than order_qty"

    try:
        db.commit()
        db.refresh(po)
    except IntegrityError:
        db.rollback()
        return None, "Purchase order already exists"

    return po, None
