import PortalMobile
import XCTest
@testable import PortalMembro

final class PortalMembroTests: XCTestCase {
    func testDebugAPIBaseURLPointsToLocalhost() {
        #if DEBUG
        XCTAssertEqual(AppConfig.apiBaseURL.scheme, "http")
        XCTAssertTrue(
            AppConfig.apiBaseURL.host == "127.0.0.1" || AppConfig.apiBaseURL.host == "localhost"
        )
        #else
        XCTAssertEqual(AppConfig.apiBaseURL.scheme, "https")
        #endif
    }

    func testPortalMobileClientCanBeConstructed() {
        let client = PortalAPIClient(baseURL: AppConfig.apiBaseURL)
        XCTAssertEqual(client.baseURL, AppConfig.apiBaseURL)
    }

    func testStatusBadges() {
        XCTAssertEqual(PartituraStatusKind(apiValue: "available").label, "Disponível")
        XCTAssertTrue(PartituraStatusKind(apiValue: "available").canOpenPDF)
        XCTAssertEqual(PartituraStatusKind(apiValue: "not_yet_available").label, "Ainda não")
        XCTAssertFalse(PartituraStatusKind(apiValue: "not_yet_available").canOpenPDF)
        XCTAssertEqual(PartituraStatusKind(apiValue: "expired").label, "Expirada")
        XCTAssertFalse(PartituraStatusKind(apiValue: "expired").canOpenPDF)
    }
}
