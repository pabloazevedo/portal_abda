"""
SearchIndex — Gerencia indexação SQLite FTS para busca rápida de documentos.
"""

import sqlite3
from pathlib import Path
from typing import Optional, List


class DocumentoSearchIndex:
    """
    Índice de busca full-text usando SQLite FTS5.
    Permite busca rápida por título, compositor, instrumento, etc.
    """

    def __init__(self, db_path: str = "uploads/search_index.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._criar_tabela()

    def _criar_tabela(self):
        """Cria tabela FTS5 se não existir."""
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS docs_search USING fts5(
                documento_id,
                arranjo_id,
                titulo_obra,
                compositor,
                tipo_documento,
                instrumento,
                caminho_arquivo,
                tokenize = 'porter'
            )
        """)
        self.conn.commit()

    def indexar(self, documento_id: int, arranjo_id: int, titulo_obra: str,
                compositor: str, tipo_documento: str, instrumento: str,
                caminho_arquivo: str):
        """
        Adiciona documento ao índice.

        Args:
            documento_id: ID do ArranjoDocumento
            arranjo_id: ID do Arranjo
            titulo_obra: Título da obra
            compositor: Nome do compositor
            tipo_documento: grade, instrumento, coral, etc
            instrumento: Nome do instrumento (para partes)
            caminho_arquivo: Caminho do arquivo
        """
        self.conn.execute("""
            INSERT INTO docs_search
            (documento_id, arranjo_id, titulo_obra, compositor,
             tipo_documento, instrumento, caminho_arquivo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (documento_id, arranjo_id, titulo_obra, compositor,
              tipo_documento, instrumento, caminho_arquivo))
        self.conn.commit()

    def buscar(self, termo: str, limite: int = 50) -> List[dict]:
        """
        Busca por termo usando FTS.

        Args:
            termo: Termo de busca
            limite: Número máximo de resultados

        Returns:
            Lista de documentos encontrados
        """
        cursor = self.conn.execute("""
            SELECT * FROM docs_search
            WHERE docs_search MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (termo, limite))

        return [dict(row) for row in cursor.fetchall()]

    def deletar(self, documento_id: int):
        """Remove documento do índice."""
        self.conn.execute(
            "DELETE FROM docs_search WHERE documento_id = ?",
            (documento_id,)
        )
        self.conn.commit()

    def deletar_por_arranjo(self, arranjo_id: int):
        """Remove todos os documentos de um arranjo do índice."""
        self.conn.execute(
            "DELETE FROM docs_search WHERE arranjo_id = ?",
            (arranjo_id,)
        )
        self.conn.commit()

    def reconstruir_todos(self, documentos):
        """
        Reconstrói o índice completo com todos os documentos.

        Args:
            documentos: Lista de ArranjoDocumento do banco
        """
        self.conn.execute("DELETE FROM docs_search")
        self.conn.commit()

        for doc in documentos:
            titulo = doc.arranjo.titulo_arranjo or ""
            compositor = doc.arranjo.obra.compositor_nome if doc.arranjo.obra else ""
            self.indexar(
                documento_id=doc.id,
                arranjo_id=doc.arranjo_id,
                titulo_obra=titulo,
                compositor=compositor,
                tipo_documento=doc.tipo,
                instrumento=doc.instrumento_nome or "",
                caminho_arquivo=doc.arquivo_caminho
            )

    def close(self):
        """Fecha a conexão com o banco."""
        self.conn.close()

    def __del__(self):
        """Garante que a conexão seja fechada."""
        try:
            self.close()
        except:
            pass
