"""Kansanmuisti — Suomen poliittisten päättäjien julkisen toiminnan kartoitus.

Paketin osat:
  collect/  — datankeruu Eduskunnan avoimesta datasta (resumable)
  analyze/  — läpinäkyvä analyysiputki (aiheet, linjaus, johdonmukaisuus)
  web/      — FastAPI-pohjainen käyttöliittymä

Periaate: jokaisella väitteellä on lähde, tulkinta erotetaan faktasta, ei motiiviväitteitä.
"""

__version__ = "0.1.0"
