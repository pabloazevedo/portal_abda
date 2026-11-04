import SwiftUI

struct RootView: View {
    @StateObject private var session = AppSession()

    var body: some View {
        Group {
            switch session.phase {
            case .bootstrapping:
                ProgressView("Carregando…")
            case .loggedOut:
                LoginView()
            case .loggedIn:
                PartiturasListView()
            }
        }
        .environmentObject(session)
        .task {
            await session.bootstrap()
        }
    }
}
