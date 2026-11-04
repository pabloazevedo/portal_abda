import SwiftUI

enum PartituraStatusKind: String {
    case available
    case notYetAvailable = "not_yet_available"
    case expired
    case unknown

    init(apiValue: String) {
        self = PartituraStatusKind(rawValue: apiValue) ?? .unknown
    }

    var label: String {
        switch self {
        case .available: return "Disponível"
        case .notYetAvailable: return "Ainda não"
        case .expired: return "Expirada"
        case .unknown: return "—"
        }
    }

    var tint: Color {
        switch self {
        case .available: return .green
        case .notYetAvailable: return .orange
        case .expired: return .secondary
        case .unknown: return .gray
        }
    }

    var canOpenPDF: Bool { self == .available }
}

struct PartituraStatusBadge: View {
    let status: String

    private var kind: PartituraStatusKind { PartituraStatusKind(apiValue: status) }

    var body: some View {
        Text(kind.label)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(kind.tint.opacity(0.15))
            .foregroundStyle(kind.tint)
            .clipShape(Capsule())
    }
}
