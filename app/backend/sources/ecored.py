"""ecored.org source — stub.

ecored.org has usable provider listing/detail pages (name, rubros, dirección,
localidad, teléfono, website) but email is hidden behind a JS button and the
site shows signs of compromise. Registered so it can be selected explicitly,
but not included in `DEFAULT_SOURCES` and not yet implemented — building the
category/province ID maps this source needs is lower priority than the other
sources.
"""

from typing import Iterator

from . import register_source


@register_source("ecored")
def iter_leads(*, tipo_cliente: str = "lead", **_kwargs) -> Iterator[dict]:
    raise NotImplementedError("ecored source is not yet implemented")
