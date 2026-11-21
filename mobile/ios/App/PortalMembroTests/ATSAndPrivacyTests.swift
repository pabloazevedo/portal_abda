import Foundation
import XCTest
@testable import PortalMembro

final class ATSAndPrivacyTests: XCTestCase {
    func testReleaseInfoPlistHasNoHTTPExceptions() throws {
        let url = Bundle.main.bundleURL
            .deletingLastPathComponent() // Products
            // Prefer source-of-truth files checked into the repo via test host path heuristics:
        let repoInfo = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent() // PortalMembroTests
            .deletingLastPathComponent() // App
            .appendingPathComponent("PortalMembro/Info.plist")
        let data = try Data(contentsOf: repoInfo)
        let plist = try PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any]
        let ats = plist?["NSAppTransportSecurity"] as? [String: Any]
        XCTAssertNotNil(ats)
        XCTAssertEqual(ats?["NSAllowsArbitraryLoads"] as? Bool, false)
        XCTAssertNil(ats?["NSExceptionDomains"], "Release não deve listar exception domains HTTP")
        XCTAssertNil(ats?["NSAllowsLocalNetworking"], "Local networking só no Info-Debug.plist")
    }

    func testDebugInfoPlistAllowsLocalHTTP() throws {
        let repoInfo = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("PortalMembro/Info-Debug.plist")
        let data = try Data(contentsOf: repoInfo)
        let plist = try PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any]
        let ats = plist?["NSAppTransportSecurity"] as? [String: Any]
        XCTAssertEqual(ats?["NSAllowsLocalNetworking"] as? Bool, true)
        let domains = ats?["NSExceptionDomains"] as? [String: Any]
        XCTAssertNotNil(domains?["localhost"])
        XCTAssertNotNil(domains?["127.0.0.1"])
    }

    func testPrivacyManifestDeclaresNoTracking() throws {
        let privacy = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("PortalMembro/PrivacyInfo.xcprivacy")
        let data = try Data(contentsOf: privacy)
        let plist = try PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any]
        XCTAssertEqual(plist?["NSPrivacyTracking"] as? Bool, false)
        let types = plist?["NSPrivacyCollectedDataTypes"] as? [[String: Any]] ?? []
        XCTAssertFalse(types.isEmpty, "Nutrition Labels: tipos de dados de conta")
        for t in types {
            XCTAssertEqual(t["NSPrivacyCollectedDataTypeTracking"] as? Bool, false)
        }
    }

    func testNoTokenLoggingFlag() {
        XCTAssertFalse(AppConfig.logsTokensOrPII)
    }

    func testAppIconAssetPresent() {
        let icon = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("PortalMembro/Assets.xcassets/AppIcon.appiconset/AppIcon.png")
        XCTAssertTrue(FileManager.default.fileExists(atPath: icon.path))
    }
}
