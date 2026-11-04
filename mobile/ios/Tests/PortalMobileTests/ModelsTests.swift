import XCTest
@testable import PortalMobile

final class ModelsTests: XCTestCase {
    func testTokenResponseDecoding() throws {
        let json = """
        {
          "access_token": "a",
          "refresh_token": "r",
          "token_type": "Bearer",
          "expires_in": 1800,
          "user": {
            "id": 1,
            "username": "musico",
            "email": "m@test.local",
            "role": "user",
            "musician_id": 9,
            "has_musician_link": true
          }
        }
        """.data(using: .utf8)!
        let tokens = try JSONDecoder().decode(TokenResponse.self, from: json)
        XCTAssertEqual(tokens.user.musicianId, 9)
        XCTAssertTrue(tokens.user.hasMusicianLink)
    }

    func testPartiturasDecoding() throws {
        let json = """
        {
          "musician_id": 9,
          "count": 1,
          "server_time": "2026-11-03T00:00:00+00:00",
          "items": [{
            "acesso_id": 3,
            "status": "available",
            "created_at": null,
            "valid_from": null,
            "expires_at": null,
            "documento_count": 1,
            "evento": {"id": 1, "titulo": "Ensaio", "data_inicio": null, "local": null},
            "documentos": [{
              "id": 10,
              "tipo": "instrumento",
              "title": "Violino",
              "label": "Violino",
              "instrumento_nome": "Violino",
              "download_path": "/api/v1/me/partituras/3/documentos/10/pdf",
              "view_ticket_path": "/api/v1/me/partituras/3/documentos/10/view-ticket"
            }]
          }]
        }
        """.data(using: .utf8)!
        let resp = try JSONDecoder().decode(PartiturasResponse.self, from: json)
        XCTAssertEqual(resp.count, 1)
        XCTAssertEqual(resp.items.first?.status, "available")
        XCTAssertEqual(resp.items.first?.documentos.first?.id, 10)
    }
}
