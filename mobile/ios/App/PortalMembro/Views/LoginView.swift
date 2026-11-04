import SwiftUI

struct LoginView: View {
    @EnvironmentObject private var session: AppSession
    @State private var username = ""
    @State private var password = ""
    @State private var isSubmitting = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Usuário", text: $username)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .textContentType(.username)
                    SecureField("Senha", text: $password)
                        .textContentType(.password)
                } header: {
                    Text("Portal do Membro")
                } footer: {
                    Text("API: \(AppConfig.apiBaseURL.absoluteString)")
                        .font(.caption2)
                }

                if let error = session.errorMessage {
                    Section {
                        Text(error)
                            .foregroundStyle(.red)
                            .font(.footnote)
                    }
                }

                Section {
                    Button {
                        Task { await submit() }
                    } label: {
                        if isSubmitting {
                            ProgressView()
                        } else {
                            Text("Entrar")
                        }
                    }
                    .disabled(username.isEmpty || password.isEmpty || isSubmitting)
                }
            }
            .navigationTitle("Entrar")
        }
    }

    private func submit() async {
        isSubmitting = true
        defer { isSubmitting = false }
        await session.login(username: username.trimmingCharacters(in: .whitespaces), password: password)
    }
}

#Preview {
    LoginView()
        .environmentObject(AppSession())
}
