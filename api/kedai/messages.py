"""WhatsApp order message sent to suppliers. Always English, as the standard trade language.

Edit the wording here. Placeholders: {supplier}, {shop}, {area}, {lines}, {date}.
Each order line uses LINE, with {product}, {quantity} and {unit}.
"""

from datetime import date

LINE = "- {product} x {quantity} {unit}"

ORDER_MESSAGE = "Hi {supplier}, this is {shop} ({area}).\nOrder please:\n{lines}\nDeliver by {date} if possible. Thank you!"


def order_message(*, supplier: str, shop: str, area: str, lines: list[dict], day: date) -> str:
    body = "\n".join(
        LINE.format(product=line["names"]["en"], quantity=line["quantity"], unit=line["unit"])
        for line in lines
        if line["quantity"] > 0
    )
    return ORDER_MESSAGE.format(
        supplier=supplier, shop=shop, area=area, lines=body, date=day.strftime("%a %d %b")
    )
