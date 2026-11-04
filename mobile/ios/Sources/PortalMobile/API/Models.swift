import Foundation

public struct LoginRequest: Encodable, Sendable {
    public let username: String
    public let password: String
    public let client: String

    public init(username: String, password: String, client: String = "ios") {
        self.username = username
        self.password = password
        self.client = client
    }
}

public struct RefreshRequest: Encodable, Sendable {
    public let refreshToken: String
    public let client: String

    public init(refreshToken: String, client: String = "ios") {
        self.refreshToken = refreshToken
        self.client = client
    }

    enum CodingKeys: String, CodingKey {
        case refreshToken = "refresh_token"
        case client
    }
}

public struct LogoutRequest: Encodable, Sendable {
    public let refreshToken: String

    public init(refreshToken: String) {
        self.refreshToken = refreshToken
    }

    enum CodingKeys: String, CodingKey {
        case refreshToken = "refresh_token"
    }
}

public struct TokenResponse: Decodable, Sendable {
    public let accessToken: String
    public let refreshToken: String
    public let tokenType: String
    public let expiresIn: Int
    public let user: APIUser

    public init(
        accessToken: String,
        refreshToken: String,
        tokenType: String,
        expiresIn: Int,
        user: APIUser
    ) {
        self.accessToken = accessToken
        self.refreshToken = refreshToken
        self.tokenType = tokenType
        self.expiresIn = expiresIn
        self.user = user
    }

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
        case user
    }
}

public struct APIUser: Decodable, Sendable {
    public let id: Int
    public let username: String
    public let email: String?
    public let role: String
    public let musicianId: Int?
    public let hasMusicianLink: Bool

    public init(
        id: Int,
        username: String,
        email: String?,
        role: String,
        musicianId: Int?,
        hasMusicianLink: Bool
    ) {
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.musicianId = musicianId
        self.hasMusicianLink = hasMusicianLink
    }

    enum CodingKeys: String, CodingKey {
        case id, username, email, role
        case musicianId = "musician_id"
        case hasMusicianLink = "has_musician_link"
    }
}

public struct PartiturasResponse: Decodable, Sendable {
    public let musicianId: Int
    public let count: Int
    public let items: [PartituraAcesso]
    public let serverTime: String

    enum CodingKeys: String, CodingKey {
        case musicianId = "musician_id"
        case count, items
        case serverTime = "server_time"
    }
}

public struct PartituraAcesso: Decodable, Sendable, Identifiable {
    public var id: Int { acessoId }
    public let acessoId: Int
    public let status: String
    public let createdAt: String?
    public let validFrom: String?
    public let expiresAt: String?
    public let documentoCount: Int
    public let evento: PartituraEvento?
    public let documentos: [PartituraDocumento]

    enum CodingKeys: String, CodingKey {
        case acessoId = "acesso_id"
        case status
        case createdAt = "created_at"
        case validFrom = "valid_from"
        case expiresAt = "expires_at"
        case documentoCount = "documento_count"
        case evento, documentos
    }
}

public struct PartituraEvento: Decodable, Sendable {
    public let id: Int?
    public let titulo: String?
    public let dataInicio: String?
    public let local: String?

    enum CodingKeys: String, CodingKey {
        case id, titulo, local
        case dataInicio = "data_inicio"
    }
}

public struct PartituraDocumento: Decodable, Sendable, Identifiable {
    public let id: Int
    public let tipo: String?
    public let title: String?
    public let label: String?
    public let instrumentoNome: String?
    public let downloadPath: String?
    public let viewTicketPath: String?

    enum CodingKeys: String, CodingKey {
        case id, tipo, title, label
        case instrumentoNome = "instrumento_nome"
        case downloadPath = "download_path"
        case viewTicketPath = "view_ticket_path"
    }
}

public struct ViewTicketResponse: Decodable, Sendable {
    public let ticket: String
    public let expiresIn: Int
    public let title: String?
    public let viewUrl: String

    enum CodingKeys: String, CodingKey {
        case ticket
        case expiresIn = "expires_in"
        case title
        case viewUrl = "view_url"
    }
}

public struct APIErrorBody: Decodable, Sendable {
    public let detail: String?
}

public enum PortalAPIError: Error, LocalizedError, Sendable {
    case invalidURL
    case http(status: Int, detail: String?)
    case decoding(Error)
    case unauthorized
    case missingMusicianLink

    public var errorDescription: String? {
        switch self {
        case .invalidURL: return "URL inválida."
        case .http(let status, let detail): return detail ?? "Erro HTTP \(status)."
        case .decoding: return "Resposta inválida do servidor."
        case .unauthorized: return "Sessão expirada. Entre novamente."
        case .missingMusicianLink: return "Conta sem vínculo com membro."
        }
    }
}
