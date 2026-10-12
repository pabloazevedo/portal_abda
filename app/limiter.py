"""
Portal — Rate limiter compartilhado (S-04).
Instanciado aqui para evitar importação circular entre main.py e os routers.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
