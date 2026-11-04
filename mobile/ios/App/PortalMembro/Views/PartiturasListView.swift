import PortalMobile
import SwiftUI

struct PartiturasListView: View {
    @EnvironmentObject private var session: AppSession
    @State private var items: [PartituraAcesso] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var selectedPDF: PDFDocumentPayload?

    var body: some View {
        NavigationStack {
            Group {
                if isLoading && items.isEmpty {
                    ProgressView("Carregando partituras…")
                } else if let errorMessage, items.isEmpty {
                    emptyState(
                        title: "Não foi possível carregar",
                        systemImage: "exclamationmark.triangle",
                        message: errorMessage
                    )
                } else if items.isEmpty {
                    emptyState(
                        title: "Nenhuma partitura",
                        systemImage: "doc.richtext",
                        message: "Quando a secretaria distribuir o material do evento, ele aparece aqui."
                    )
                } else {
                    listContent
                }
            }
            .navigationTitle("Partituras")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Sair") {
                        Task { await session.logout() }
                    }
                }
            }
            .refreshable { await load(showSpinner: false) }
            .task { await load(showSpinner: true) }
            .sheet(item: $selectedPDF) { payload in
                PDFViewerScreen(payload: payload)
            }
        }
    }

    private var listContent: some View {
        List {
            if let errorMessage {
                Text(errorMessage)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }
            ForEach(items) { acesso in
                Section {
                    ForEach(acesso.documentos) { doc in
                        documentoRow(acesso: acesso, doc: doc)
                    }
                } header: {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(acesso.evento?.titulo ?? "Evento")
                                .font(.headline)
                            if let local = acesso.evento?.local, !local.isEmpty {
                                Text(local).font(.caption).foregroundStyle(.secondary)
                            }
                            if let data = acesso.evento?.dataInicio {
                                Text(data).font(.caption2).foregroundStyle(.secondary)
                            }
                        }
                        Spacer()
                        PartituraStatusBadge(status: acesso.status)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func documentoRow(acesso: PartituraAcesso, doc: PartituraDocumento) -> some View {
        let kind = PartituraStatusKind(apiValue: acesso.status)
        Button {
            Task { await openPDF(acesso: acesso, doc: doc) }
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(doc.title ?? doc.label ?? "Partitura")
                    if let tipo = doc.tipo {
                        Text(tipo).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Spacer()
                if kind.canOpenPDF {
                    Image(systemName: "doc.richtext")
                        .foregroundColor(.accentColor)
                } else {
                    Image(systemName: "lock.fill")
                        .foregroundColor(.secondary)
                }
            }
        }
        .disabled(!kind.canOpenPDF || isLoading)
    }

    private func load(showSpinner: Bool) async {
        if showSpinner { isLoading = true }
        defer { isLoading = false }
        do {
            let response = try await session.client.listPartituras()
            items = response.items
            errorMessage = nil
        } catch PortalAPIError.unauthorized {
            await session.handleUnauthorized()
        } catch PortalAPIError.missingMusicianLink {
            errorMessage = "Conta sem vínculo com membro."
            items = []
        } catch let err as PortalAPIError {
            errorMessage = err.localizedDescription
        } catch {
            errorMessage = "Falha ao listar partituras."
        }
    }

    private func openPDF(acesso: PartituraAcesso, doc: PartituraDocumento) async {
        isLoading = true
        defer { isLoading = false }
        do {
            let data = try await session.client.downloadPDF(acessoId: acesso.acessoId, documentoId: doc.id)
            selectedPDF = PDFDocumentPayload(
                id: "\(acesso.acessoId)-\(doc.id)",
                title: doc.title ?? doc.label ?? "Partitura",
                data: data
            )
            errorMessage = nil
        } catch PortalAPIError.unauthorized {
            await session.handleUnauthorized()
        } catch let err as PortalAPIError {
            errorMessage = err.localizedDescription
        } catch {
            errorMessage = "Não foi possível abrir o PDF."
        }
    }
}

struct PDFDocumentPayload: Identifiable {
    let id: String
    let title: String
    let data: Data
}

private func emptyState(title: String, systemImage: String, message: String) -> some View {
    VStack(spacing: 12) {
        Image(systemName: systemImage)
            .font(.system(size: 40))
            .foregroundColor(.secondary)
        Text(title).font(.title3.weight(.semibold))
        Text(message)
            .font(.footnote)
            .foregroundColor(.secondary)
            .multilineTextAlignment(.center)
            .padding(.horizontal)
    }
    .frame(maxWidth: .infinity, maxHeight: .infinity)
}
