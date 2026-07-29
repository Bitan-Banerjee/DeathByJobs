import SwiftUI
import AppKit
import Foundation
import Combine
import UniformTypeIdentifiers

// MARK: - Design System & Theme

struct AppTheme {
    let name: String
    let bg: Color
    let surface: Color
    let surface2: Color
    let border: Color
    let text: Color
    let muted: Color
    let accent: Color
    let accentBg: Color
    let accentDim: Color
    let errorRed: Color
    let errorRedBg: Color
    let headingFont: Font
    let monoFont: Font
    let monoLargeFont: Font
    let monoSmallFont: Font

    static func `default`() -> AppTheme {
        // Colors sampled from the reference image.png: warm cream paper,
        // near-black ink, and a muted burgundy/mauve halftone accent.
        AppTheme(
            name: "vintage",
            bg: Color(hex: "F4ECD8"),
            surface: Color(hex: "F4ECD8"),
            surface2: Color(hex: "E8E0CC"),
            border: Color(hex: "1A1A1A"),
            text: Color(hex: "1A1A1A"),
            muted: Color(hex: "5C5C5C"),
            accent: Color(hex: "9B5B6E"),
            accentBg: Color(hex: "9B5B6E"),
            accentDim: Color(hex: "9B5B6E").opacity(0.6),
            errorRed: Color(hex: "8B1A1A"),
            errorRedBg: Color(hex: "8B1A1A").opacity(0.12),
            headingFont: .system(size: 32, weight: .bold, design: .serif),
            monoFont: .system(size: 13, design: .monospaced),
            monoLargeFont: .system(size: 28, weight: .bold, design: .monospaced),
            monoSmallFont: .system(size: 10, weight: .semibold, design: .monospaced)
        )
    }
}

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0; Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default: (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(.sRGB, red: Double(r) / 255, green: Double(g) / 255, blue: Double(b) / 255, opacity: Double(a) / 255)
    }
}

/// Fine, dense dotted halftone pattern used to mimic the vintage print texture in image.png.
struct HalftonePattern: View {
    let color: Color
    let density: CGFloat // 0.0 (sparse) to 1.0 (dense)

    var body: some View {
        Canvas { context, size in
            let dotSize: CGFloat = 1.6
            let baseSpacing: CGFloat = 2.0
            let spacing = baseSpacing * (1.0 - density * 0.65)
            let numCols = Int(size.width / (dotSize + spacing)) + 2
            let numRows = Int(size.height / (dotSize + spacing)) + 2

            for row in 0..<numRows {
                for col in 0..<numCols {
                    let x = CGFloat(col) * (dotSize + spacing) + (dotSize / 2)
                    let y = CGFloat(row) * (dotSize + spacing) + (dotSize / 2)
                    let finalX = x + (row % 2 == 0 ? 0 : spacing / 2)
                    if finalX < size.width && y < size.height {
                        let rect = CGRect(x: finalX, y: y, width: dotSize, height: dotSize)
                        context.fill(Path(ellipseIn: rect), with: .color(color))
                    }
                }
            }
        }
        .clipped()
    }
}

/// Offset dotted shadow used behind cards in the reference image.
/// Rounded, dense black halftone dots shifted behind the card — no extra outline.
struct DottedShadow<Content: View>: View {
    let theme: AppTheme
    let offset: CGSize
    let borderColor: Color?
    let content: Content
    private let cornerRadius: CGFloat = 3

    init(theme: AppTheme, offset: CGSize = CGSize(width: 5, height: 5), borderColor: Color? = nil, @ViewBuilder content: () -> Content) {
        self.theme = theme
        self.offset = offset
        self.borderColor = borderColor
        self.content = content()
    }

    var body: some View {
        ZStack(alignment: .topLeading) {
            // Shadow layer: dense black halftone dots, slightly rounded
            GeometryReader { geo in
                HalftonePattern(color: theme.text.opacity(0.42), density: 0.9)
                    .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
            }
            .offset(offset)

            // Main card layer
            content
                .padding(24)
                .background(theme.surface)
                .border(borderColor ?? theme.border, width: 1)
        }
    }
}

// MARK: - Models

struct PipelineParams: Codable {
    var jobs: Int
    var target: Int
    var max_loops: Int
    var mode: String
}

struct StatusResponse: Codable {
    let status: String
    let pid: Int?
}

struct CronJob: Codable, Identifiable, Equatable {
    let id: String
    let name: String
    var enabled: Bool
    var hour: Int
    var minute: Int
    var nextRun: String?
}

struct CronResponse: Codable {
    let jobs: [CronJob]
}

struct LogsResponse: Codable {
    let lines: [String]?
}

struct ReportResponse: Codable {
    let linkedin: PlatformReport
    let naukri: PlatformReport
}

struct PlatformReport: Codable {
    let scraped: Int
    let matched: Int
    let applied: Int
    let failed: Int
}

struct OnboardingStatusResponse: Codable {
    let configured: Bool
    let profile_exists: Bool
    let providers_exists: Bool
}

struct OnboardingPayload: Codable {
    let candidate_name: String
    let candidate_email: String
    let target_role: String
    let experience_years: Int
    let experience_range: String
    let notice_period: String
    let serving_notice: Bool
    let core_skills: [String]
    let linkedin_keyword: String
    let naukri_keyword: String
    let location: String
    let match_variance: String
    let title_red_flags: [String]
    let excluded_companies: [String]
    let current_employer: String
    let provider: String
    let api_key: String
    let linkedin_email: String
    let linkedin_password: String
    let naukri_email: String
    let naukri_password: String
    let analogous_skills: [String: String]?
}

struct ConfigResponse: Codable {
    let profile: ProfileConfig
    let providers: ProvidersConfig
    let linkedin_email: String?
    let naukri_email: String?
}

struct ProfileConfig: Codable {
    let candidate: CandidateConfig
    let target_profile: TargetProfileConfig
    let search: SearchConfig
    let filters: FiltersConfig
    let application: ApplicationConfig
}

struct CandidateConfig: Codable {
    let name: String
    let email: String
}

struct TargetProfileConfig: Codable {
    let role: String
    let experience_years: Int
    let experience_range: String
    let notice_period: String
    let serving_notice: Bool
    let core_skills: [String]
}

struct SearchConfig: Codable {
    let linkedin_keyword: String
    let naukri_keyword: String
    let location: String
}

struct FiltersConfig: Codable {
    let match_variance: String
    let title: TitleFiltersConfig
    let company: CompanyFiltersConfig
}

struct TitleFiltersConfig: Codable {
    let red_flags: [String]
}

struct CompanyFiltersConfig: Codable {
    let excluded: [String]
    let current_employer: String
}

struct ApplicationConfig: Codable {
    let experience_years: Int
}

struct ProvidersConfig: Codable {
    let active_provider: String
}

// MARK: - Backend Process Manager

class BackendManager {
    static let shared = BackendManager()
    private var process: Process?
    private let projectRoot = "/Users/bitanbanerjee/Coding/GitHub_Repos/AiAutomation"
    private let baseUrl = URL(string: "http://127.0.0.1:8000/status")!

    var isAlreadyRunning: Bool = false
    var pipelineWasRunningAtLaunch: Bool = false

    func startServerIfNeeded() async {
        if await backendIsReachable() {
            isAlreadyRunning = true
            print("Native App: Backend already running.")
            return
        }
        isAlreadyRunning = false
        pipelineWasRunningAtLaunch = lockFileExistsWithLiveProcess()
        await launchServer()
    }

    private func backendIsReachable() async -> Bool {
        var request = URLRequest(url: baseUrl)
        request.timeoutInterval = 1.5
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    private func launchServer() async {
        killPort8000()
        let pythonPath = findPythonPath()
        let p = Process()
        p.executableURL = URL(fileURLWithPath: pythonPath)
        p.currentDirectoryURL = URL(fileURLWithPath: projectRoot)
        let pythonCmd = "import sys, uvicorn; sys.path.insert(0, '\(projectRoot)'); uvicorn.run('src.api.main:app', host='127.0.0.1', port=8000, log_level='warning')"
        p.arguments = ["-u", "-c", pythonCmd]

        let logDir = "\(projectRoot)/logs"
        try? FileManager.default.createDirectory(atPath: logDir, withIntermediateDirectories: true)
        let logPath = "\(logDir)/app_launch.log"
        FileManager.default.createFile(atPath: logPath, contents: nil)
        if let fileHandle = FileHandle(forWritingAtPath: logPath) {
            p.standardOutput = fileHandle
            p.standardError = fileHandle
        }

        self.process = p
        do {
            try p.run()
        } catch {
            print("Native App Error: Failed to start FastAPI server: \(error)")
            return
        }

        // Wait up to ~10 seconds for the server to respond
        for _ in 0..<20 {
            if await backendIsReachable() { return }
            try? await Task.sleep(nanoseconds: 500_000_000)
        }
        print("Native App Warning: Backend did not become reachable in time.")
    }

    func stopServer() {
        if let p = process, p.isRunning {
            p.terminate()
            p.waitUntilExit()
        }
        killPort8000()
    }

    private func killPort8000() {
        let sh = Process()
        sh.executableURL = URL(fileURLWithPath: "/bin/sh")
        sh.arguments = ["-c", "lsof -ti :8000 | xargs kill -9 2>/dev/null || true"]
        try? sh.run()
        sh.waitUntilExit()
    }

    private func findPythonPath() -> String {
        let customPath = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12"
        if FileManager.default.fileExists(atPath: customPath) { return customPath }
        let commonPaths = ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]
        for path in commonPaths { if FileManager.default.fileExists(atPath: path) { return path } }
        return "python3"
    }

    private func lockFilePath() -> String {
        "\(projectRoot)/app.lock"
    }

    private func lockFileExistsWithLiveProcess() -> Bool {
        let path = lockFilePath()
        guard FileManager.default.fileExists(atPath: path) else { return false }
        guard let contents = try? String(contentsOfFile: path, encoding: .utf8),
              let pid = Int(contents.trimmingCharacters(in: .whitespacesAndNewlines)) else { return false }
        return processIsAlive(pid)
    }

    private func processIsAlive(_ pid: Int) -> Bool {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/kill")
        task.arguments = ["-0", String(pid)]
        do {
            try task.run()
            task.waitUntilExit()
            return task.terminationStatus == 0
        } catch {
            return false
        }
    }

    /// Synchronous reachability check used during app termination.
    func backendIsReachableNow() -> Bool {
        var request = URLRequest(url: baseUrl)
        request.timeoutInterval = 1.5
        let semaphore = DispatchSemaphore(value: 0)
        var reachable = false
        let task = URLSession.shared.dataTask(with: request) { _, response, _ in
            reachable = (response as? HTTPURLResponse)?.statusCode == 200
            semaphore.signal()
        }
        task.resume()
        _ = semaphore.wait(timeout: .now() + 2)
        return reachable
    }

    /// Synchronous pipeline-running check used during app termination.
    func pipelineIsRunningNow() -> Bool {
        // Prefer the API's own view of status.
        guard let statusUrl = URL(string: "http://127.0.0.1:8000/status") else { return lockFileExistsWithLiveProcess() }
        var request = URLRequest(url: statusUrl)
        request.timeoutInterval = 1.5
        let semaphore = DispatchSemaphore(value: 0)
        var running = false
        let task = URLSession.shared.dataTask(with: request) { data, response, _ in
            if let data = data,
               (response as? HTTPURLResponse)?.statusCode == 200,
               let decoded = try? JSONDecoder().decode(StatusResponse.self, from: data),
               decoded.status == "running" {
                running = true
            }
            semaphore.signal()
        }
        task.resume()
        _ = semaphore.wait(timeout: .now() + 2)
        return running || lockFileExistsWithLiveProcess()
    }
}

// MARK: - View Model

class PipelineViewModel: ObservableObject {
    @Published var status: String = "idle"
    @Published var backendReachable: Bool = false
    @Published var backendStarting: Bool = true
    @Published var backendStartedByApp: Bool = false
    @Published var logs: [String] = []
    @Published var cronJobs: [CronJob] = []
    @Published var report: ReportResponse? = nil
    @Published var page: String = "dashboard"
    @Published var jobs: Int = 25
    @Published var target: Int = 50
    @Published var maxLoops: Int = 4
    @Published var mode: String = "quota"
    @Published var errorMessage: String? = nil
    @Published var onboardingConfigured: Bool = true
    @Published var onboardingCheckComplete: Bool = false
    @Published var currentConfig: ConfigResponse? = nil

    private var cancellables = Set<AnyCancellable>()
    private let baseUrl = "http://127.0.0.1:8000"
    private var timer: Timer? = nil

    init() { }

    func prepareBackend() async {
        await BackendManager.shared.startServerIfNeeded()
        backendStartedByApp = !BackendManager.shared.isAlreadyRunning
        backendStarting = false
        await checkOnboardingStatus()
        startPolling()
    }

    @MainActor
    func checkOnboardingStatus() async {
        do {
            let (data, response) = try await URLSession.shared.data(from: URL(string: "\(baseUrl)/onboarding/status")!)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { return }
            let decoded = try JSONDecoder().decode(OnboardingStatusResponse.self, from: data)
            onboardingConfigured = decoded.configured
        } catch {
            onboardingConfigured = true
        }
        onboardingCheckComplete = true
    }

    @MainActor
    func loadConfig() async {
        do {
            let (data, response) = try await URLSession.shared.data(from: URL(string: "\(baseUrl)/config")!)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { return }
            currentConfig = try JSONDecoder().decode(ConfigResponse.self, from: data)
        } catch {
            currentConfig = nil
        }
    }

    func startPolling() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { [weak self] _ in
            Task { [weak self] in
                await self?.refreshAll()
            }
        }
        Task { await refreshAll() }
    }

    func stopPolling() {
        timer?.invalidate()
        timer = nil
    }

    @MainActor
    func refreshAll() async {
        async let statusTask: () = refreshStatus()
        async let logsTask: () = refreshLogs()
        async let cronTask: () = refreshCron()
        async let reportTask: () = refreshReport()
        _ = await (statusTask, logsTask, cronTask, reportTask)
    }

    @MainActor
    func refreshStatus() async {
        do {
            let url = URL(string: "\(baseUrl)/status?t=\(Int(Date().timeIntervalSince1970))")!
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                backendReachable = false
                return
            }
            let decoded = try JSONDecoder().decode(StatusResponse.self, from: data)
            status = decoded.status
            backendReachable = true
            errorMessage = nil
        } catch {
            backendReachable = false
        }
    }

    @MainActor
    func refreshLogs() async {
        do {
            var components = URLComponents(string: "\(baseUrl)/logs")!
            components.queryItems = [URLQueryItem(name: "lines", value: "200"), URLQueryItem(name: "t", value: String(Int(Date().timeIntervalSince1970)))]
            let (data, response) = try await URLSession.shared.data(from: components.url!)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { return }
            let decoded = try JSONDecoder().decode(LogsResponse.self, from: data)
            logs = decoded.lines ?? []
        } catch {
            // Logs non-critical
        }
    }

    @MainActor
    func refreshCron() async {
        do {
            let url = URL(string: "\(baseUrl)/cron?t=\(Int(Date().timeIntervalSince1970))")!
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { return }
            let decoded = try JSONDecoder().decode(CronResponse.self, from: data)
            cronJobs = decoded.jobs
        } catch {
            cronJobs = []
        }
    }

    @MainActor
    func refreshReport() async {
        do {
            let url = URL(string: "\(baseUrl)/report?t=\(Int(Date().timeIntervalSince1970))")!
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { return }
            let decoded = try JSONDecoder().decode(ReportResponse.self, from: data)
            report = decoded
        } catch {
            report = nil
        }
    }

    func startPipeline() {
        guard backendReachable else {
            errorMessage = "Backend is not reachable. Start the API server first."
            return
        }
        guard let url = URL(string: "\(baseUrl)/start") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        let params = PipelineParams(
            jobs: jobs,
            target: target,
            max_loops: maxLoops,
            mode: mode
        )
        request.httpBody = try? JSONEncoder().encode(params)

        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    self?.errorMessage = "Start failed: \(error.localizedDescription)"
                    self?.status = "error"
                } else {
                    self?.status = "running"
                }
            }
        }.resume()
    }

    func stopPipeline() {
        guard let url = URL(string: "\(baseUrl)/stop") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    self?.errorMessage = "Stop failed: \(error.localizedDescription)"
                }
                self?.status = "idle"
            }
        }.resume()
    }

    func updateCron(jobId: String, enabled: Bool?, hour: Int?, minute: Int?) {
        guard let url = URL(string: "\(baseUrl)/cron") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "job_id": jobId,
            "enabled": enabled as Any,
            "hour": hour as Any,
            "minute": minute as Any
        ].compactMapValues { $0 }

        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    self?.errorMessage = "Schedule update failed: \(error.localizedDescription)"
                }
                Task { await self?.refreshCron() }
            }
        }.resume()
    }

    func triggerCron(jobId: String) {
        guard let url = URL(string: "\(baseUrl)/scheduler/trigger") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    self?.errorMessage = "Run now failed: \(error.localizedDescription)"
                }
            }
        }.resume()
    }

    func submitOnboarding(_ payload: OnboardingPayload, completion: @escaping (Bool, String?) -> Void) {
        guard let url = URL(string: "\(baseUrl)/onboarding") else {
            completion(false, "Invalid URL")
            return
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONEncoder().encode(payload)

        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    completion(false, error.localizedDescription)
                    return
                }
                guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                    let msg = data.flatMap { String(data: $0, encoding: .utf8) } ?? "Save failed"
                    completion(false, msg)
                    return
                }
                self?.onboardingConfigured = true
                completion(true, nil)
            }
        }.resume()
    }

    func uploadResume(url: URL, completion: @escaping (Bool, String?) -> Void) {
        guard let endpoint = URL(string: "\(baseUrl)/upload-resume") else {
            completion(false, "Invalid URL")
            return
        }
        guard let fileData = try? Data(contentsOf: url) else {
            completion(false, "Could not read resume file")
            return
        }

        let payload: [String: String] = [
            "filename": url.lastPathComponent,
            "data": fileData.base64EncodedString()
        ]

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)

        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    completion(false, error.localizedDescription)
                    return
                }
                guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                    completion(false, "Upload failed")
                    return
                }
                completion(true, nil)
            }
        }.resume()
    }

    func deriveResume(completion: @escaping (Bool, String?) -> Void) {
        guard let url = URL(string: "\(baseUrl)/derive-resume") else {
            completion(false, "Invalid URL")
            return
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    completion(false, error.localizedDescription)
                    return
                }
                guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                    let msg = data.flatMap { String(data: $0, encoding: .utf8) } ?? "Derivation failed"
                    completion(false, msg)
                    return
                }
                completion(true, nil)
            }
        }.resume()
    }
}

// MARK: - Themed Components

struct ThemedCard<Content: View>: View {
    let theme: AppTheme
    var borderColor: Color? = nil
    let content: Content

    init(theme: AppTheme, borderColor: Color? = nil, @ViewBuilder content: () -> Content) {
        self.theme = theme; self.borderColor = borderColor; self.content = content()
    }

    var body: some View {
        DottedShadow(theme: theme, offset: CGSize(width: 6, height: 6), borderColor: borderColor) {
            content
        }
    }
}

struct ThemedButtonStyle: ButtonStyle {
    let variant: ButtonVariant
    let theme: AppTheme
    let isDisabled: Bool
    enum ButtonVariant { case accent, red, ghost, saveSmall, accentSmall }

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: (variant == .saveSmall || variant == .accentSmall) ? 11 : 13, weight: .semibold, design: .monospaced))
            .foregroundColor(foreground(isPressed: configuration.isPressed))
            .padding(.horizontal, (variant == .saveSmall || variant == .accentSmall) ? 12 : 18)
            .padding(.vertical, (variant == .saveSmall || variant == .accentSmall) ? 4 : 9)
            .background(backgroundColor(isPressed: configuration.isPressed))
            .border(border(isPressed: configuration.isPressed), width: 1)
            .scaleEffect(configuration.isPressed && !isDisabled ? 0.97 : 1.0)
    }

    private func foreground(isPressed: Bool) -> Color {
        if isDisabled {
            return theme.muted
        }
        switch variant {
        case .accent, .accentSmall: return theme.bg
        default: return theme.text
        }
    }

    private func backgroundColor(isPressed: Bool) -> Color {
        if isDisabled {
            return theme.surface2.opacity(0.7)
        }
        switch variant {
        case .accent, .accentSmall: return isPressed ? theme.accent.opacity(0.85) : theme.accent
        case .red: return isPressed ? theme.errorRed.opacity(0.15) : theme.errorRedBg
        default: return isPressed ? theme.surface2.opacity(0.85) : theme.surface2
        }
    }

    private func border(isPressed: Bool) -> Color {
        if isDisabled {
            return theme.border.opacity(0.5)
        }
        switch variant {
        case .accent, .accentSmall: return theme.accent
        case .red: return theme.errorRed
        default: return theme.border
        }
    }
}

struct ThemedToggle: View {
    @Binding var isOn: Bool
    let theme: AppTheme
    var body: some View {
        Button(action: { isOn.toggle() }) {
            ZStack(alignment: isOn ? .trailing : .leading) {
                Rectangle()
                    .fill(isOn ? theme.accent : theme.surface2)
                    .frame(width: 44, height: 24)
                    .border(isOn ? theme.accent : theme.border, width: 1)

                Rectangle()
                    .fill(isOn ? theme.bg : theme.text.opacity(0.7))
                    .frame(width: 18, height: 18)
                    .padding(.horizontal, 2)
            }
        }
        .buttonStyle(.plain)
        .focusable(false)
    }
}

// MARK: - Custom Themed Dropdown

struct ThemedDropdown: View {
    let items: [(String, String)] // (value, label)
    @Binding var selection: String
    let theme: AppTheme

    @State private var isOpen: Bool = false

    var body: some View {
        VStack(spacing: 0) {
            Button(action: { isOpen.toggle() }) {
                HStack {
                    Text(displayName)
                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                        .foregroundColor(theme.text)
                    Spacer()
                    Image(systemName: isOpen ? "chevron.up" : "chevron.down")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(theme.muted)
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
                .background(theme.surface2)
                .border(theme.border, width: 1)
            }
            .buttonStyle(.plain)
            .focusable(false)

            if isOpen {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(items, id: \.0) { item in
                        Button(action: {
                            selection = item.0
                            isOpen = false
                        }) {
                            HStack {
                                Text(item.1)
                                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                                    .foregroundColor(selection == item.0 ? theme.bg : theme.text)
                                Spacer()
                                if selection == item.0 {
                                    Image(systemName: "checkmark")
                                        .font(.system(size: 10, weight: .bold))
                                        .foregroundColor(theme.bg)
                                }
                            }
                            .padding(.horizontal, 10)
                            .padding(.vertical, 8)
                            .background(selection == item.0 ? theme.accent : theme.surface)
                        }
                        .buttonStyle(.plain)
                        .focusable(false)
                        .overlay(
                            Rectangle()
                                .frame(height: 1)
                                .foregroundColor(theme.border.opacity(0.5)),
                            alignment: .bottom
                        )
                    }
                }
                .background(theme.surface)
                .border(theme.border, width: 1)
                .shadow(color: theme.text.opacity(0.15), radius: 4, x: 0, y: 3)
            }
        }
    }

    private var displayName: String {
        items.first(where: { $0.0 == selection })?.1 ?? "Select"
    }
}

// MARK: - Tag Input Field

struct TagInputField: View {
    let label: String
    @Binding var commaSeparatedText: String
    let theme: AppTheme
    @State private var newTag: String = ""

    private var tags: [String] {
        commaSeparatedText.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label.uppercased()).font(theme.monoSmallFont).foregroundColor(theme.muted)

            if !tags.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(tags, id: \.self) { tag in
                            HStack(spacing: 4) {
                                Text(tag)
                                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                                    .foregroundColor(theme.text)
                                    .lineLimit(1)
                                Button(action: { removeTag(tag) }) {
                                    Image(systemName: "xmark")
                                        .font(.system(size: 8, weight: .bold))
                                        .foregroundColor(theme.muted)
                                }
                                .buttonStyle(.plain)
                                .focusable(false)
                            }
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(theme.surface2)
                            .border(theme.border, width: 1)
                        }
                    }
                }
            }

            HStack(spacing: 6) {
                ZStack(alignment: .leading) {
                    if newTag.isEmpty {
                        Text("Type and press Add")
                            .font(.system(size: 13, weight: .semibold, design: .monospaced))
                            .foregroundColor(theme.muted)
                            .padding(.leading, 8)
                            .allowsHitTesting(false)
                    }
                    TextField("", text: $newTag)
                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                        .foregroundColor(theme.text)
                        .textFieldStyle(.plain)
                        .padding(.leading, 8)
                }
                .padding(.vertical, 8)
                .padding(.horizontal, 8)
                .background(theme.surface2)
                .border(theme.border, width: 1)
                .onSubmit { addTag() }

                Button("Add") { addTag() }
                    .buttonStyle(ThemedButtonStyle(variant: .saveSmall, theme: theme, isDisabled: newTag.trimmingCharacters(in: .whitespaces).isEmpty))
                    .disabled(newTag.trimmingCharacters(in: .whitespaces).isEmpty)
                    .focusable(false)
            }
        }
    }

    private func addTag() {
        let trimmed = newTag.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        var current = tags
        if !current.contains(trimmed) {
            current.append(trimmed)
            commaSeparatedText = current.joined(separator: ", ")
        }
        newTag = ""
    }

    private func removeTag(_ tag: String) {
        var current = tags
        current.removeAll { $0 == tag }
        commaSeparatedText = current.joined(separator: ", ")
    }
}

// MARK: - Subviews

struct LogoView: View {
    let theme: AppTheme

    private var logoImage: NSImage? {
        // Try the app bundle Resources first, then fall back to the project root.
        let candidates = [
            Bundle.main.url(forResource: "logo", withExtension: "png"),
            URL(fileURLWithPath: "/Users/bitanbanerjee/Coding/GitHub_Repos/AiAutomation/logo.png")
        ]
        for url in candidates.compactMap({ $0 }) {
            if let image = NSImage(contentsOf: url) { return image }
        }
        return nil
    }

    var body: some View {
        Group {
            if let image = logoImage {
                Image(nsImage: image)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(width: 54, height: 54)
            } else {
                ZStack {
                    Rectangle().fill(theme.text.opacity(0.1)).frame(width: 32, height: 32)
                    HStack(spacing: 2) {
                        Text(">").font(.system(size: 16, weight: .bold, design: .monospaced))
                        Rectangle().fill(theme.text).frame(width: 6, height: 3).offset(y: 4)
                    }.foregroundColor(theme.text)
                }
            }
        }
    }
}

struct StatusPillView: View {
    let status: String
    let theme: AppTheme
    var body: some View {
        HStack(spacing: 8) {
            Circle().fill(dotColor).frame(width: 8, height: 8)
            Text(status.uppercased()).font(.system(size: 11, weight: .bold, design: .monospaced)).tracking(0.6)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(
            ZStack {
                pillBg

            }
        )
        .foregroundColor(pillFg)
        .border(pillBorder, width: 2)
    }

    private var dotColor: Color {
        switch status.lowercased() {
        case "running": return theme.bg
        case "error": return theme.errorRed
        default: return theme.muted
        }
    }
    private var pillBg: Color {
        switch status.lowercased() {
        case "running": return theme.accentBg
        case "error": return theme.errorRedBg
        default: return theme.surface2
        }
    }
    private var pillFg: Color {
        switch status.lowercased() {
        case "running": return theme.bg
        case "error": return theme.errorRed
        default: return theme.muted
        }
    }
    private var pillBorder: Color {
        switch status.lowercased() {
        case "running": return theme.accent
        case "error": return theme.errorRed
        default: return theme.border
        }
    }
}

struct StatBoxView: View {
    let label: String, value: String, isAccent: Bool, theme: AppTheme
    var body: some View {
        DottedShadow(theme: theme, borderColor: theme.border) {
            VStack(alignment: .leading, spacing: 10) {
                Text(label.uppercased()).font(theme.monoSmallFont).tracking(1.0).foregroundColor(theme.muted)
                Text(value).font(theme.monoLargeFont).foregroundColor(isAccent ? theme.accent : theme.text).lineLimit(1)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct StageNodeView: View {
    let label: String, iconName: String, isActive: Bool, isDone: Bool, theme: AppTheme
    var body: some View {
        VStack(spacing: 10) {
            ZStack {
                Rectangle()
                    .fill(boxBackground)
                    .frame(width: 52, height: 52)
                    .border(boxBorder, width: 1)

                Image(systemName: iconName)
                    .font(.system(size: 20))
                    .foregroundColor(iconColor)
            }
            Text(label.uppercased())
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .tracking(0.8)
                .foregroundColor(isActive || isDone ? theme.text : theme.muted)
                .multilineTextAlignment(.center)
        }
    }

    private var boxBackground: Color {
        if isActive { return Color(hex: "F5D76E") }       // warm yellow
        if isDone   { return theme.accent }                // burgundy
        return theme.surface                               // cream
    }

    private var boxBorder: Color {
        if isActive { return Color(hex: "D4A017") }        // darker yellow border
        if isDone   { return theme.accent }                // burgundy
        return theme.border                                // black
    }

    private var iconColor: Color {
        if isActive { return theme.text }                  // dark icon on yellow
        if isDone   { return theme.bg }                    // white icon on burgundy
        return theme.muted                                 // muted on cream
    }
}

struct StageLineView: View {
    let isDone: Bool
    let theme: AppTheme
    var body: some View { Rectangle().fill(isDone ? theme.accent : theme.border).frame(height: 2).frame(maxWidth: .infinity).padding(.bottom, 24) }
}

struct LogLineView: View {
    let line: String
    let theme: AppTheme
    var body: some View {
        Text(line.isEmpty ? " " : line)
            .font(.system(size: 11, design: .monospaced))
            .foregroundColor(textColor)
            .lineLimit(nil)
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
    private var textColor: Color {
        if line.contains("FAILURE") || line.contains("CRITICAL") { return theme.errorRed }
        if line.contains("✅") { return theme.accent }
        if line.contains("⚠️") { return theme.errorRed.opacity(0.8) }
        return theme.text
    }
}

struct CronRowView: View {
    let job: CronJob
    let theme: AppTheme
    let onUpdate: (Bool?, Int?, Int?) -> Void
    let onRunNow: () -> Void

    @State private var hourStr: String
    @State private var minuteStr: String

    init(job: CronJob, theme: AppTheme, onUpdate: @escaping (Bool?, Int?, Int?) -> Void, onRunNow: @escaping () -> Void) {
        self.job = job; self.theme = theme; self.onUpdate = onUpdate; self.onRunNow = onRunNow
        _hourStr = State(initialValue: String(format: "%02d", job.hour))
        _minuteStr = State(initialValue: String(format: "%02d", job.minute))
    }

    var body: some View {
        HStack(spacing: 16) {
            ThemedToggle(
                isOn: Binding(
                    get: { job.enabled },
                    set: { onUpdate($0, nil, nil) }
                ),
                theme: theme
            )
            VStack(alignment: .leading, spacing: 3) {
                Text(job.name).font(.system(size: 14, weight: .semibold, design: .monospaced)).foregroundColor(theme.text)
                Text(job.enabled ? "Runs daily at \(String(format: "%02d", job.hour)):\(String(format: "%02d", job.minute))" : "Disabled")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundColor(theme.muted)
                if let nextRun = job.nextRun {
                    Text("Next: \(nextRun)")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(theme.accent)
                }
            }
            Spacer()
            HStack(spacing: 6) {
                TextField("", text: $hourStr, onEditingChanged: { isEditing in
                    if !isEditing {
                        if let val = Int(hourStr) {
                            hourStr = String(format: "%02d", min(max(val, 0), 23))
                        } else {
                            hourStr = String(format: "%02d", job.hour)
                        }
                    }
                }, onCommit: {})
                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                    .foregroundColor(theme.text)
                    .multilineTextAlignment(.center)
                    .padding(4)
                    .background(theme.surface2)
                    .border(theme.border, width: 2)
                    .frame(width: 56)
                    .textFieldStyle(.plain)
                    .onReceive(Just(hourStr)) { newValue in
                        let filtered = newValue.filter { "0123456789".contains($0) }
                        if filtered != newValue { hourStr = filtered }
                        if filtered.count > 2 { hourStr = String(filtered.prefix(2)) }
                    }

                Text(":").font(.system(size: 13, weight: .bold, design: .monospaced)).foregroundColor(theme.muted)

                TextField("", text: $minuteStr, onEditingChanged: { isEditing in
                    if !isEditing {
                        if let val = Int(minuteStr) {
                            minuteStr = String(format: "%02d", min(max(val, 0), 59))
                        } else {
                            minuteStr = String(format: "%02d", job.minute)
                        }
                    }
                }, onCommit: {})
                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                    .foregroundColor(theme.text)
                    .multilineTextAlignment(.center)
                    .padding(4)
                    .background(theme.surface2)
                    .border(theme.border, width: 2)
                    .frame(width: 56)
                    .textFieldStyle(.plain)
                    .onReceive(Just(minuteStr)) { newValue in
                        let filtered = newValue.filter { "0123456789".contains($0) }
                        if filtered != newValue { minuteStr = filtered }
                        if filtered.count > 2 { minuteStr = String(filtered.prefix(2)) }
                    }

                Text("24H")
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundColor(theme.muted)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(theme.surface2)
                    .border(theme.border, width: 1)

                if isDirty {
                    Button("Save") {
                        let h = max(0, min(Int(hourStr) ?? job.hour, 23))
                        let m = max(0, min(Int(minuteStr) ?? job.minute, 59))
                        hourStr = String(format: "%02d", h)
                        minuteStr = String(format: "%02d", m)
                        onUpdate(nil, h, m)
                    }
                    .buttonStyle(ThemedButtonStyle(variant: .saveSmall, theme: theme, isDisabled: false))
                    .focusable(false)
                }

                Button("Run Now") {
                    onRunNow()
                }
                .buttonStyle(ThemedButtonStyle(variant: .accentSmall, theme: theme, isDisabled: false))
                .focusable(false)
            }
        }
        .padding(.vertical, 16)
        .overlay(Rectangle().frame(height: 1).foregroundColor(theme.border), alignment: .bottom)
    }

    private var isDirty: Bool {
        hourStr != String(format: "%02d", job.hour) || minuteStr != String(format: "%02d", job.minute)
    }
}

// MARK: - Sidebar

struct SidebarView: View {
    @ObservedObject var viewModel: PipelineViewModel
    let theme: AppTheme

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                LogoView(theme: theme)
                Text("AI-PIPELINE").font(.system(size: 16, weight: .bold, design: .monospaced)).tracking(0.8).foregroundColor(theme.text)
            }
            .padding([.horizontal, .top], 24)
            .padding(.bottom, 32)

            VStack(spacing: 2) {
                SidebarButton(title: "Dashboard", icon: "square.grid.2x2.fill", page: "dashboard", current: $viewModel.page, theme: theme)
                SidebarButton(title: "Schedule", icon: "calendar", page: "schedule", current: $viewModel.page, theme: theme)
                SidebarButton(title: "Logs", icon: "doc.text", page: "logs", current: $viewModel.page, theme: theme)
                SidebarButton(title: "Settings", icon: "gearshape", page: "settings", current: $viewModel.page, theme: theme)
            }
            .padding(.horizontal, 12)

            Spacer()

            VStack(spacing: 12) {
                if !viewModel.backendReachable {
                    HStack(spacing: 6) {
                        Image(systemName: "exclamationmark.triangle.fill")
                        Text("OFFLINE").font(.system(size: 10, weight: .bold, design: .monospaced))
                    }
                    .foregroundColor(theme.errorRed)
                    .padding(.vertical, 6)
                }
                StatusPillView(status: viewModel.status, theme: theme)
            }
            .padding(.horizontal, 24)
            .padding(.top, 20)
            .border(theme.border, width: 1)
            .padding(.bottom, 24)
        }
        .frame(width: 220)
        .background(theme.bg)
    }
}

struct SidebarButton: View {
    let title: String
    let icon: String
    let page: String
    @Binding var current: String
    let theme: AppTheme

    var body: some View {
        Button(action: { current = page }) {
            HStack(spacing: 10) {
                Image(systemName: icon)
                Text(title)
            }
        }
        .buttonStyle(SidebarButtonStyle(isActive: current == page, theme: theme))
        .focusable(false)
    }
}

struct SidebarButtonStyle: ButtonStyle {
    let isActive: Bool, theme: AppTheme

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold, design: .monospaced))
            .foregroundColor(isActive ? theme.text : (configuration.isPressed ? theme.text : theme.muted))
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 12).padding(.vertical, 12)
            .background(
                ZStack {
                    isActive ? theme.surface2 : (configuration.isPressed ? theme.surface2.opacity(0.5) : Color.clear)
                    if isActive {
                        HalftonePattern(color: theme.accent.opacity(0.12), density: 0.75)
                    }
                }
            )
            .border(isActive ? theme.border : Color.clear, width: 1)
            .contentShape(Rectangle())
    }
}

// MARK: - Dashboard

struct DashboardView: View {
    @ObservedObject var viewModel: PipelineViewModel
    let theme: AppTheme

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Dashboard").font(theme.headingFont).foregroundColor(theme.text)
                Text("Monitor and control your job automation pipeline").font(theme.monoFont).foregroundColor(theme.muted)
            }
            .padding(.bottom, 36)

            if let error = viewModel.errorMessage {
                ThemedCard(theme: theme, borderColor: theme.errorRed) {
                    HStack(spacing: 10) {
                        Image(systemName: "exclamationmark.octagon.fill").foregroundColor(theme.errorRed)
                        Text(error).font(theme.monoFont).foregroundColor(theme.errorRed)
                        Spacer()
                        Button("Dismiss") { viewModel.errorMessage = nil }
                            .buttonStyle(ThemedButtonStyle(variant: .ghost, theme: theme, isDisabled: false))
                    }
                }
                .padding(.bottom, 20)
            }

            if !viewModel.backendReachable && !viewModel.backendStarting {
                ThemedCard(theme: theme, borderColor: theme.errorRed) {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack(spacing: 8) {
                            Image(systemName: "wifi.slash").foregroundColor(theme.errorRed)
                            Text("Backend Offline").font(.system(size: 14, weight: .bold, design: .monospaced)).foregroundColor(theme.errorRed)
                        }
                        Text("The pipeline engine could not be started automatically. Restart the app, or start it manually with:")
                            .font(theme.monoFont)
                            .foregroundColor(theme.text)
                        Text("python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000")
                            .font(theme.monoFont)
                            .foregroundColor(theme.accent)
                            .padding(8)
                            .background(theme.surface2)
                            .border(theme.border, width: 1)
                    }
                }
                .padding(.bottom, 20)
            }

            HStack(spacing: 14) {
                StatBoxView(label: "Target Today", value: "\(viewModel.target)", isAccent: true, theme: theme)
                StatBoxView(label: "Max Loops", value: "\(viewModel.maxLoops)", isAccent: false, theme: theme)
                StatBoxView(label: "Pipeline", value: viewModel.status.capitalized, isAccent: viewModel.status == "running", theme: theme)
            }
            .padding(.bottom, 20)

            if let report = viewModel.report {
                ThemedCard(theme: theme) {
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Today’s Pipeline Report").font(.system(size: 11, weight: .bold, design: .monospaced)).tracking(1.2).foregroundColor(theme.muted)
                        HStack(spacing: 14) {
                            PlatformStatView(title: "LinkedIn", report: report.linkedin, theme: theme)
                            PlatformStatView(title: "Naukri", report: report.naukri, theme: theme)
                        }
                    }
                }
                .padding(.bottom, 20)
            }

            ThemedCard(theme: theme) {
                VStack(alignment: .leading, spacing: 24) {
                    Text("Pipeline Stages").font(.system(size: 11, weight: .bold, design: .monospaced)).tracking(1.2).foregroundColor(theme.muted)
                    pipelineStages
                }
            }
            .padding(.bottom, 20)

            ThemedCard(theme: theme) {
                VStack(alignment: .leading, spacing: 24) {
                    Text("Run Pipeline")
                        .font(.system(size: 11, weight: .bold, design: .monospaced))
                        .tracking(1.2)
                        .foregroundColor(theme.muted)

                    VStack(alignment: .leading, spacing: 14) {
                        // Custom mode selector to avoid system segmented picker color issues
                        HStack(spacing: 0) {
                            ModeButton(title: "Daily Quota", value: "quota", selection: $viewModel.mode, theme: theme, fontSize: 13)
                                .frame(maxWidth: .infinity, minHeight: 40, maxHeight: 40)
                            ModeButton(title: "Single Test", value: "single_test", selection: $viewModel.mode, theme: theme, fontSize: 13)
                                .frame(maxWidth: .infinity, minHeight: 40, maxHeight: 40)
                            ModeButton(title: "Resume", value: "resume", selection: $viewModel.mode, theme: theme, fontSize: 13)
                                .frame(maxWidth: .infinity, minHeight: 40, maxHeight: 40)
                        }
                        .frame(height: 40)

                        HStack(spacing: 14) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("TARGET").font(theme.monoSmallFont).foregroundColor(theme.muted)
                                TextField("", value: $viewModel.target, format: .number)
                                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                                    .foregroundColor(theme.text)
                                    .frame(width: 80)
                                    .padding(6)
                                    .background(theme.surface2)
                                    .border(theme.border, width: 1)
                                    .textFieldStyle(.plain)
                            }
                            VStack(alignment: .leading, spacing: 4) {
                                Text("MAX LOOPS").font(theme.monoSmallFont).foregroundColor(theme.muted)
                                TextField("", value: $viewModel.maxLoops, format: .number)
                                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                                    .foregroundColor(theme.text)
                                    .frame(width: 80)
                                    .padding(6)
                                    .background(theme.surface2)
                                    .border(theme.border, width: 1)
                                    .textFieldStyle(.plain)
                            }
                            VStack(alignment: .leading, spacing: 4) {
                                Text("JOBS/BATCH").font(theme.monoSmallFont).foregroundColor(theme.muted)
                                TextField("", value: $viewModel.jobs, format: .number)
                                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                                    .foregroundColor(theme.text)
                                    .frame(width: 80)
                                    .padding(6)
                                    .background(theme.surface2)
                                    .border(theme.border, width: 1)
                                    .textFieldStyle(.plain)
                            }
                            Spacer()
                        }

                        HStack(spacing: 10) {
            Button(action: { viewModel.startPipeline() }) {
                HStack(spacing: 7) { Image(systemName: "play.fill"); Text("Start") }
            }
            .buttonStyle(ThemedButtonStyle(variant: .accent, theme: theme, isDisabled: viewModel.status == "running" || !viewModel.backendReachable))
            .disabled(viewModel.status == "running" || !viewModel.backendReachable)
            .focusable(false)

            Button(action: { viewModel.stopPipeline() }) {
                HStack(spacing: 7) { Image(systemName: "stop.fill"); Text("Stop") }
            }
            .buttonStyle(ThemedButtonStyle(variant: .red, theme: theme, isDisabled: viewModel.status != "running"))
            .disabled(viewModel.status != "running")
            .focusable(false)
                        }
                    }
                }
            }
        }
    }

    private var pipelineStages: some View {
        let activeStage = stageIndex(from: viewModel.status, logs: viewModel.logs)
        return HStack(spacing: 0) {
            StageNodeView(label: "Scrape", iconName: "globe", isActive: activeStage == 0, isDone: activeStage > 0, theme: theme)
            StageLineView(isDone: activeStage > 0, theme: theme)
            StageNodeView(label: "AI Filter", iconName: "line.3.horizontal.decrease", isActive: activeStage == 1, isDone: activeStage > 1, theme: theme)
            StageLineView(isDone: activeStage > 1, theme: theme)
            StageNodeView(label: "Tailor", iconName: "pencil.and.outline", isActive: activeStage == 2, isDone: activeStage > 2, theme: theme)
            StageLineView(isDone: activeStage > 2, theme: theme)
            StageNodeView(label: "Apply", iconName: "paperplane.fill", isActive: activeStage == 3, isDone: activeStage > 3, theme: theme)
            StageLineView(isDone: activeStage > 3, theme: theme)
            StageNodeView(label: "Export", iconName: "square.and.arrow.down", isActive: activeStage == 4, isDone: activeStage > 4, theme: theme)
        }
        .padding(.horizontal, 10)
    }

    private func stageIndex(from status: String, logs: [String]) -> Int {
        guard status == "running" else { return -1 }
        let keywords: [(String, Int)] = [
            ("STAGE 4/4 ✅ Export complete", 4),
            ("STAGE 3/4 ✅ Auto-Applying complete", 3),
            ("STAGE 3/5 ✅ Tailoring complete", 2),
            ("STAGE 2/5 ✅ Filtering complete", 1),
            ("STAGE 1/5 ✅ Scraping complete", 0)
        ]
        for (keyword, idx) in keywords {
            if logs.contains(where: { $0.contains(keyword) }) { return idx }
        }
        return 0
    }
}

struct ModeButton: View {
    let title: String
    let value: String
    @Binding var selection: String
    let theme: AppTheme
    var fontSize: CGFloat = 11

    var body: some View {
        Button(action: { selection = value }) {
            Text(title)
                .font(.system(size: fontSize, weight: .semibold, design: .monospaced))
                .foregroundColor(isSelected ? theme.bg : theme.text)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.7)
                .padding(.horizontal, 6)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(isSelected ? theme.accent : theme.surface2)
                .border(theme.border, width: 1)
        }
        .buttonStyle(.plain)
        .focusable(false)
    }

    private var isSelected: Bool { selection == value }
}

struct PlatformStatView: View {
    let title: String
    let report: PlatformReport
    let theme: AppTheme

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title.uppercased()).font(.system(size: 11, weight: .bold, design: .monospaced)).tracking(0.8).foregroundColor(theme.muted)
            HStack(spacing: 12) {
                miniStat(label: "Scraped", value: report.scraped)
                miniStat(label: "Matched", value: report.matched)
                miniStat(label: "Applied", value: report.applied)
                miniStat(label: "Failed", value: report.failed)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(theme.surface2)
        .border(theme.border, width: 1)
    }

    private func miniStat(label: String, value: Int) -> some View {
        VStack(spacing: 4) {
            Text("\(value)").font(.system(size: 18, weight: .bold, design: .monospaced)).foregroundColor(theme.text)
            Text(label).font(.system(size: 9, weight: .semibold, design: .monospaced)).foregroundColor(theme.muted)
        }
    }
}

// MARK: - Schedule Page

struct ScheduleView: View {
    @ObservedObject var viewModel: PipelineViewModel
    let theme: AppTheme

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Schedule").font(theme.headingFont).foregroundColor(theme.text)
                Text("Manage daily cron jobs").font(theme.monoFont).foregroundColor(theme.muted)
            }
            .padding(.bottom, 36)

            if !viewModel.backendReachable {
                backendOfflineBanner
                    .padding(.bottom, 20)
            }

            ThemedCard(theme: theme) {
                VStack(alignment: .leading, spacing: 0) {
                    if viewModel.cronJobs.isEmpty {
                        Text("No scheduled jobs found. Add them via data/schedule.json.")
                            .font(theme.monoFont)
                            .foregroundColor(theme.muted)
                            .padding(.vertical, 20)
                    } else {
                        ForEach(viewModel.cronJobs) { job in
                            CronRowView(job: job, theme: theme, onUpdate: { enabled, hour, minute in
                                viewModel.updateCron(jobId: job.id, enabled: enabled, hour: hour, minute: minute)
                            }, onRunNow: {
                                viewModel.triggerCron(jobId: job.id)
                            })
                        }
                    }
                }
            }
        }
    }

    private var backendOfflineBanner: some View {
        ThemedCard(theme: theme, borderColor: theme.errorRed) {
            HStack(spacing: 10) {
                Image(systemName: "wifi.slash").foregroundColor(theme.errorRed)
                Text("Backend offline — schedule updates will not work.")
                    .font(theme.monoFont)
                    .foregroundColor(theme.errorRed)
            }
        }
    }
}

// MARK: - Logs Page

struct LogsView: View {
    @ObservedObject var viewModel: PipelineViewModel
    let theme: AppTheme

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Logs").font(theme.headingFont).foregroundColor(theme.text)
                Text("Live pipeline output").font(theme.monoFont).foregroundColor(theme.muted)
            }
            .padding(.bottom, 36)

            if !viewModel.backendReachable {
                backendOfflineBanner
                    .padding(.bottom, 20)
            }

            ThemedCard(theme: theme) {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 3) {
                            ForEach(Array(viewModel.logs.enumerated()), id: \.offset) { _, line in
                                LogLineView(line: line, theme: theme)
                            }
                        }
                        .id("logBottom")
                    }
                    .frame(minHeight: 400)
                    .onChange(of: viewModel.logs.count) {
                        withAnimation { proxy.scrollTo("logBottom", anchor: .bottom) }
                    }
                }
            }
        }
    }

    private var backendOfflineBanner: some View {
        ThemedCard(theme: theme, borderColor: theme.errorRed) {
            HStack(spacing: 10) {
                Image(systemName: "wifi.slash").foregroundColor(theme.errorRed)
                Text("Backend offline — start `python3 src/api/main.py` to see logs.")
                    .font(theme.monoFont)
                    .foregroundColor(theme.errorRed)
            }
        }
    }
}

// MARK: - Onboarding

struct OnboardingView: View {
    @ObservedObject var viewModel: PipelineViewModel
    @Binding var isPresented: Bool
    let theme: AppTheme

    @State private var candidateName: String = ""
    @State private var candidateEmail: String = ""
    @State private var targetRole: String = "Data Engineer"
    @State private var experienceYears: String = "4"
    @State private var experienceRange: String = "0 to 5 years"
    @State private var noticePeriod: String = "30 days"
    @State private var servingNotice: Bool = false
    @State private var coreSkills: String = "Python, SQL, PySpark, AWS"
    @State private var linkedinKeyword: String = "Data Engineer"
    @State private var naukriKeyword: String = "Data Engineer"
    @State private var location: String = "India"
    @State private var matchVariance: String = "moderate"
    @State private var titleRedFlags: String = "director, manager, vp, lead, head, principal, frontend, front-end, ui, ux, ios, android, mobile, react, angular, full stack, full-stack, qa, test, support"
    @State private var excludedCompanies: String = "Turing"
    @State private var currentEmployer: String = ""
    @State private var provider: String = "gemini"
    @State private var apiKey: String = ""
    @State private var showApiKey: Bool = false
    @State private var linkedinEmail: String = ""
    @State private var linkedinPassword: String = ""
    @State private var naukriEmail: String = ""
    @State private var naukriPassword: String = ""
    @State private var resumeURL: URL? = nil
    @State private var isSaving: Bool = false
    @State private var errorText: String? = nil
    @State private var derivedResume: Bool = false
    @State private var showSuccess: Bool = false
    @State private var scrollToTop: Bool = false

    private let providers = [
        ("gemini", "Google Gemini"),
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic Claude"),
        ("local", "Local / Ollama")
    ]

    private var providerDisplayName: String {
        providers.first(where: { $0.0 == provider })?.1 ?? "Select Provider"
    }

    private let varianceLevels = [
        ("strict", "Strict — exact tools only"),
        ("moderate", "Moderate — allow similar tools"),
        ("loose", "Loose — broad domain match")
    ]

    var body: some View {
        ScrollViewReader { proxy in
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Welcome").font(theme.headingFont).foregroundColor(theme.text)
                    Text("Set up your profile so the pipeline can find jobs that fit you.").font(theme.monoFont).foregroundColor(theme.muted)
                }
                .id("top")
                .padding(.bottom, 32)

                if let error = errorText {
                    ThemedCard(theme: theme, borderColor: theme.errorRed) {
                        HStack(spacing: 8) {
                            Image(systemName: "exclamationmark.octagon.fill").foregroundColor(theme.errorRed)
                            Text(error).font(theme.monoFont).foregroundColor(theme.errorRed)
                            Spacer()
                        }
                    }
                    .padding(.bottom, 20)
                }

                if showSuccess {
                    ThemedCard(theme: theme, borderColor: theme.accent) {
                        HStack(spacing: 8) {
                            Image(systemName: "checkmark.circle.fill").foregroundColor(theme.accent)
                            Text("Profile saved! Closing…").font(theme.monoFont).foregroundColor(theme.accent)
                            Spacer()
                        }
                    }
                    .padding(.bottom, 20)
                }

                ThemedCard(theme: theme) {
                    VStack(alignment: .leading, spacing: 16) {
                        sectionTitle("Candidate")
                        HStack(spacing: 14) {
                            labeledTextField("Full Name", text: $candidateName)
                            labeledTextField("Email", text: $candidateEmail)
                        }
                        HStack(spacing: 14) {
                            labeledTextField("Experience Years", text: $experienceYears, width: 120)
                            labeledTextField("Open to Roles", text: $experienceRange, placeholder: "e.g. 0 to 5 years")
                        }
                        HStack(spacing: 14) {
                            labeledTextField("Notice Period", text: $noticePeriod, width: 140)
                            VStack(alignment: .leading, spacing: 4) {
                                Text("SERVING NOTICE").font(theme.monoSmallFont).foregroundColor(theme.muted)
                                ThemedToggle(isOn: $servingNotice, theme: theme)
                            }
                        }
                        TagInputField(label: "Core Skills", commaSeparatedText: $coreSkills, theme: theme)
                    }
                }
                .padding(.bottom, 20)

                ThemedCard(theme: theme) {
                    VStack(alignment: .leading, spacing: 16) {
                        sectionTitle("Target Job")
                        HStack(spacing: 14) {
                            labeledTextField("Target Role", text: $targetRole)
                            labeledTextField("Location", text: $location, width: 150)
                        }
                        HStack(spacing: 14) {
                            labeledTextField("LinkedIn Keyword", text: $linkedinKeyword)
                            labeledTextField("Naukri Keyword", text: $naukriKeyword)
                        }

                        TagInputField(label: "Titles/Roles to Avoid", commaSeparatedText: $titleRedFlags, theme: theme)

                        VStack(alignment: .leading, spacing: 8) {
                            Text("MATCH VARIANCE").font(theme.monoSmallFont).foregroundColor(theme.muted)
                            HStack(spacing: 0) {
                                ForEach(Array(varianceLevels.enumerated()), id: \.offset) { _, level in
                                    ModeButton(title: level.1, value: level.0, selection: $matchVariance, theme: theme)
                                        .frame(maxWidth: .infinity, minHeight: 52, maxHeight: 52)
                                }
                            }
                            .frame(maxWidth: .infinity)
                            .frame(height: 52)
                        }
                    }
                }
                .padding(.bottom, 20)

                ThemedCard(theme: theme) {
                    VStack(alignment: .leading, spacing: 16) {
                        sectionTitle("Company Filters")
                        labeledTextField("Current Employer", text: $currentEmployer)
                        labeledTextField("Excluded Companies (comma separated)", text: $excludedCompanies)
                    }
                }
                .padding(.bottom, 20)

                ThemedCard(theme: theme) {
                    VStack(alignment: .leading, spacing: 16) {
                        sectionTitle("Platform Credentials")
                        HStack(spacing: 14) {
                            labeledTextField("LinkedIn Email", text: $linkedinEmail)
                            labeledSecureField("LinkedIn Password", text: $linkedinPassword, placeholder: "Password")
                        }
                        HStack(spacing: 14) {
                            labeledTextField("Naukri Email", text: $naukriEmail)
                            labeledSecureField("Naukri Password", text: $naukriPassword, placeholder: "Password")
                        }
                    }
                }
                .padding(.bottom, 20)

                ThemedCard(theme: theme) {
                    VStack(alignment: .leading, spacing: 16) {
                        sectionTitle("AI Provider")
                        VStack(alignment: .leading, spacing: 8) {
                            Text("PROVIDER").font(theme.monoSmallFont).foregroundColor(theme.muted)
                            ThemedDropdown(
                                items: providers,
                                selection: $provider,
                                theme: theme
                            )
                            .frame(width: 260)
                        }

                        VStack(alignment: .leading, spacing: 4) {
                            Text("API KEY").font(theme.monoSmallFont).foregroundColor(theme.muted)
                            HStack(spacing: 0) {
                                ZStack(alignment: .leading) {
                                    if apiKey.isEmpty {
                                        Text("Paste your API key here")
                                            .font(.system(size: 13, weight: .semibold, design: .monospaced))
                                            .foregroundColor(theme.muted)
                                            .padding(.leading, 8)
                                            .allowsHitTesting(false)
                                    }
                                    Group {
                                        if showApiKey {
                                            TextField("", text: $apiKey)
                                        } else {
                                            SecureField("", text: $apiKey)
                                        }
                                    }
                                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                                    .foregroundColor(theme.text)
                                    .textFieldStyle(.plain)
                                    .padding(.leading, 8)
                                }
                                .frame(maxWidth: .infinity, maxHeight: .infinity)

                                Button(action: { showApiKey.toggle() }) {
                                    Image(systemName: showApiKey ? "eye.slash" : "eye")
                                        .foregroundColor(theme.muted)
                                }
                                .buttonStyle(.plain)
                                .focusable(false)
                                .padding(.trailing, 8)
                            }
                            .background(theme.surface2)
                            .border(theme.border, width: 1)
                            .frame(height: 34)
                        }
                    }
                }
                .padding(.bottom, 20)

                ThemedCard(theme: theme) {
                    VStack(alignment: .leading, spacing: 16) {
                        sectionTitle("Resume")
                        HStack(spacing: 12) {
                            Button("Choose resume.docx") {
                                let panel = NSOpenPanel()
                                if #available(macOS 11.0, *) {
                                    if let docxType = UTType(filenameExtension: "docx") {
                                        panel.allowedContentTypes = [docxType]
                                    }
                                } else {
                                    panel.allowedFileTypes = ["docx"]
                                }
                                panel.allowsMultipleSelection = false
                                if panel.runModal() == .OK {
                                    resumeURL = panel.url
                                }
                            }
                            .buttonStyle(ThemedButtonStyle(variant: .ghost, theme: theme, isDisabled: false))
                            .focusable(false)

                            if let url = resumeURL {
                                Text(url.lastPathComponent)
                                    .font(theme.monoFont)
                                    .foregroundColor(theme.muted)
                                    .lineLimit(1)
                            } else {
                                Text("No file selected")
                                    .font(theme.monoFont)
                                    .foregroundColor(theme.muted)
                            }

                            Spacer()
                        }

                        if derivedResume {
                            HStack(spacing: 6) {
                                Image(systemName: "checkmark.circle.fill").foregroundColor(theme.accent)
                                Text("base_resume.md derived from resume.docx")
                                    .font(theme.monoFont)
                                    .foregroundColor(theme.accent)
                            }
                        }
                    }
                }
                .padding(.bottom, 24)

                HStack {
                    Spacer()
                    Button(action: saveOnboarding) {
                        HStack(spacing: 8) {
                            if isSaving { ProgressView().scaleEffect(0.7).tint(theme.bg) }
                            Text(isSaving ? "Saving…" : "Save & Continue")
                        }
                    }
                    .buttonStyle(ThemedButtonStyle(variant: .accent, theme: theme, isDisabled: isSaving || !isValid))
                    .disabled(isSaving || !isValid)
                    .focusable(false)
                }
            }
            .padding(40)
            .frame(maxWidth: 700, alignment: .topLeading)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(theme.bg)
        .onChange(of: scrollToTop) { _, _ in
            withAnimation { proxy.scrollTo("top", anchor: .top) }
        }
        }
    }

    private var isValid: Bool {
        !candidateName.isEmpty && !targetRole.isEmpty && !apiKey.isEmpty && resumeURL != nil && !experienceYears.isEmpty
    }

    private func labeledSecureField(_ label: String, text: Binding<String>, placeholder: String = "") -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label.uppercased()).font(theme.monoSmallFont).foregroundColor(theme.muted)
            ZStack(alignment: .leading) {
                if text.wrappedValue.isEmpty {
                    Text(placeholder)
                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                        .foregroundColor(theme.muted)
                        .padding(.leading, 8)
                        .allowsHitTesting(false)
                }
                SecureField("", text: text)
                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                    .foregroundColor(theme.text)
                    .textFieldStyle(.plain)
                    .padding(.leading, 8)
            }
            .padding(.vertical, 8)
            .background(theme.surface2)
            .border(theme.border, width: 1)
        }
    }

    private func sectionTitle(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.system(size: 11, weight: .bold, design: .monospaced))
            .tracking(1.2)
            .foregroundColor(theme.muted)
    }

    private func labeledTextField(_ label: String, text: Binding<String>, placeholder: String = "", width: CGFloat? = nil) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label.uppercased()).font(theme.monoSmallFont).foregroundColor(theme.muted)
            TextField(placeholder, text: text)
                .font(.system(size: 13, weight: .semibold, design: .monospaced))
                .foregroundColor(theme.text)
                .frame(width: width)
                .padding(8)
                .background(theme.surface2)
                .border(theme.border, width: 1)
                .textFieldStyle(.plain)
        }
    }

    private func saveOnboarding() {
        guard let resumeURL = resumeURL else { return }
        isSaving = true
        errorText = nil

        // 1. Save profile + provider + API key first so backend has the key.
        let payload = OnboardingPayload(
            candidate_name: self.candidateName,
            candidate_email: self.candidateEmail,
            target_role: self.targetRole,
            experience_years: Int(self.experienceYears) ?? 4,
            experience_range: self.experienceRange,
            notice_period: self.noticePeriod,
            serving_notice: self.servingNotice,
            core_skills: self.coreSkills.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty },
            linkedin_keyword: self.linkedinKeyword,
            naukri_keyword: self.naukriKeyword,
            location: self.location,
            match_variance: self.matchVariance,
            title_red_flags: self.titleRedFlags.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty },
            excluded_companies: self.excludedCompanies.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty },
            current_employer: self.currentEmployer,
            provider: self.provider,
            api_key: self.apiKey,
            linkedin_email: self.linkedinEmail,
            linkedin_password: self.linkedinPassword,
            naukri_email: self.naukriEmail,
            naukri_password: self.naukriPassword,
            analogous_skills: nil
        )

        self.viewModel.submitOnboarding(payload) { saved, saveError in
            guard saved else {
                self.isSaving = false
                self.errorText = saveError ?? "Failed to save profile"
                return
            }

            // 2. Upload resume now that the backend knows which provider/key to use.
            self.viewModel.uploadResume(url: resumeURL) { uploaded, uploadError in
                guard uploaded else {
                    self.isSaving = false
                    self.errorText = uploadError ?? "Resume upload failed"
                    return
                }

                // 3. Derive base_resume.md from resume.docx.
                self.viewModel.deriveResume { derived, deriveError in
                    self.isSaving = false
                    guard derived else {
                        self.errorText = deriveError ?? "Could not derive base_resume.md"
                        return
                    }
                    self.derivedResume = true

                    // 4. Show success, then close onboarding.
                    self.showSuccess = true
                    self.scrollToTop.toggle()
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                        self.viewModel.onboardingConfigured = true
                        self.isPresented = false
                    }
                }
            }
        }
    }
}

// MARK: - Settings

struct SettingsView: View {
    @ObservedObject var viewModel: PipelineViewModel
    let theme: AppTheme

    @State private var candidateName: String = ""
    @State private var candidateEmail: String = ""
    @State private var targetRole: String = ""
    @State private var experienceYears: String = ""
    @State private var experienceRange: String = ""
    @State private var noticePeriod: String = ""
    @State private var servingNotice: Bool = false
    @State private var coreSkills: String = ""
    @State private var linkedinKeyword: String = ""
    @State private var naukriKeyword: String = ""
    @State private var location: String = ""
    @State private var matchVariance: String = "moderate"
    @State private var titleRedFlags: String = ""
    @State private var excludedCompanies: String = ""
    @State private var currentEmployer: String = ""
    @State private var provider: String = "gemini"
    @State private var apiKey: String = ""
    @State private var showApiKey: Bool = false
    @State private var linkedinEmail: String = ""
    @State private var linkedinPassword: String = ""
    @State private var naukriEmail: String = ""
    @State private var naukriPassword: String = ""
    @State private var resumeURL: URL? = nil
    @State private var isSaving: Bool = false
    @State private var saveMessage: String? = nil
    @State private var saveError: String? = nil
    @State private var scrollToTop: Bool = false

    private let providers = [
        ("gemini", "Google Gemini"),
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic Claude"),
        ("local", "Local / Ollama")
    ]

    private let varianceLevels = [
        ("strict", "Strict — exact tools only"),
        ("moderate", "Moderate — allow similar tools"),
        ("loose", "Loose — broad domain match")
    ]

    var body: some View {
        ScrollViewReader { proxy in
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Settings").font(theme.headingFont).foregroundColor(theme.text)
                    Text("Edit your profile, provider, and filters at any time.").font(theme.monoFont).foregroundColor(theme.muted)
                }
                .id("top")
                .padding(.bottom, 32)

                if let error = saveError {
                    ThemedCard(theme: theme, borderColor: theme.errorRed) {
                        HStack(spacing: 8) {
                            Image(systemName: "exclamationmark.octagon.fill").foregroundColor(theme.errorRed)
                            Text(error).font(theme.monoFont).foregroundColor(theme.errorRed)
                            Spacer()
                        }
                    }
                    .padding(.bottom, 20)
                }

                if let message = saveMessage {
                    ThemedCard(theme: theme, borderColor: theme.accent) {
                        HStack(spacing: 8) {
                            Image(systemName: "checkmark.circle.fill").foregroundColor(theme.accent)
                            Text(message).font(theme.monoFont).foregroundColor(theme.accent)
                            Spacer()
                        }
                    }
                    .padding(.bottom, 20)
                }

                ThemedCard(theme: theme) {
                    VStack(alignment: .leading, spacing: 16) {
                        sectionTitle("Candidate")
                        HStack(spacing: 14) {
                            labeledTextField("Full Name", text: $candidateName)
                            labeledTextField("Email", text: $candidateEmail)
                        }
                        HStack(spacing: 14) {
                            labeledTextField("Experience Years", text: $experienceYears, width: 120)
                            labeledTextField("Open to Roles", text: $experienceRange, placeholder: "e.g. 0 to 5 years")
                        }
                        HStack(spacing: 14) {
                            labeledTextField("Notice Period", text: $noticePeriod, width: 140)
                            VStack(alignment: .leading, spacing: 4) {
                                Text("SERVING NOTICE").font(theme.monoSmallFont).foregroundColor(theme.muted)
                                ThemedToggle(isOn: $servingNotice, theme: theme)
                            }
                        }
                        TagInputField(label: "Core Skills", commaSeparatedText: $coreSkills, theme: theme)
                    }
                }
                .padding(.bottom, 20)

                ThemedCard(theme: theme) {
                    VStack(alignment: .leading, spacing: 16) {
                        sectionTitle("Target Job")
                        HStack(spacing: 14) {
                            labeledTextField("Target Role", text: $targetRole)
                            labeledTextField("Location", text: $location, width: 150)
                        }
                        HStack(spacing: 14) {
                            labeledTextField("LinkedIn Keyword", text: $linkedinKeyword)
                            labeledTextField("Naukri Keyword", text: $naukriKeyword)
                        }

                        TagInputField(label: "Titles/Roles to Avoid", commaSeparatedText: $titleRedFlags, theme: theme)

                        VStack(alignment: .leading, spacing: 8) {
                            Text("MATCH VARIANCE").font(theme.monoSmallFont).foregroundColor(theme.muted)
                            HStack(spacing: 0) {
                                ForEach(Array(varianceLevels.enumerated()), id: \.offset) { _, level in
                                    ModeButton(title: level.1, value: level.0, selection: $matchVariance, theme: theme)
                                        .frame(maxWidth: .infinity, minHeight: 52, maxHeight: 52)
                                }
                            }
                            .frame(maxWidth: .infinity)
                            .frame(height: 52)
                        }
                    }
                }
                .padding(.bottom, 20)

                ThemedCard(theme: theme) {
                    VStack(alignment: .leading, spacing: 16) {
                        sectionTitle("Company Filters")
                        labeledTextField("Current Employer", text: $currentEmployer)
                        labeledTextField("Excluded Companies (comma separated)", text: $excludedCompanies)
                    }
                }
                .padding(.bottom, 20)

                ThemedCard(theme: theme) {
                    VStack(alignment: .leading, spacing: 16) {
                        sectionTitle("Platform Credentials")
                        HStack(spacing: 14) {
                            labeledTextField("LinkedIn Email", text: $linkedinEmail)
                            labeledSecureField("LinkedIn Password", text: $linkedinPassword, placeholder: "Password")
                        }
                        HStack(spacing: 14) {
                            labeledTextField("Naukri Email", text: $naukriEmail)
                            labeledSecureField("Naukri Password", text: $naukriPassword, placeholder: "Password")
                        }
                    }
                }
                .padding(.bottom, 20)

                ThemedCard(theme: theme) {
                    VStack(alignment: .leading, spacing: 16) {
                        sectionTitle("AI Provider")
                        VStack(alignment: .leading, spacing: 8) {
                            Text("PROVIDER").font(theme.monoSmallFont).foregroundColor(theme.muted)
                            ThemedDropdown(
                                items: providers,
                                selection: $provider,
                                theme: theme
                            )
                            .frame(width: 260)
                        }

                        VStack(alignment: .leading, spacing: 4) {
                            Text("API KEY").font(theme.monoSmallFont).foregroundColor(theme.muted)
                            Text("Leave blank to keep your existing API key.").font(.system(size: 10, design: .monospaced)).foregroundColor(theme.muted)
                            HStack(spacing: 0) {
                                ZStack(alignment: .leading) {
                                    if apiKey.isEmpty {
                                        Text("Paste new API key to change, or leave blank")
                                            .font(.system(size: 13, weight: .semibold, design: .monospaced))
                                            .foregroundColor(theme.muted)
                                            .padding(.leading, 8)
                                            .allowsHitTesting(false)
                                    }
                                    Group {
                                        if showApiKey {
                                            TextField("", text: $apiKey)
                                        } else {
                                            SecureField("", text: $apiKey)
                                        }
                                    }
                                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                                    .foregroundColor(theme.text)
                                    .textFieldStyle(.plain)
                                    .padding(.leading, 8)
                                }
                                .frame(maxWidth: .infinity, maxHeight: .infinity)

                                Button(action: { showApiKey.toggle() }) {
                                    Image(systemName: showApiKey ? "eye.slash" : "eye")
                                        .foregroundColor(theme.muted)
                                }
                                .buttonStyle(.plain)
                                .focusable(false)
                                .padding(.trailing, 8)
                            }
                            .background(theme.surface2)
                            .border(theme.border, width: 1)
                            .frame(height: 34)
                        }
                    }
                }
                .padding(.bottom, 20)

                HStack {
                    Spacer()
                    Button(action: saveSettings) {
                        HStack(spacing: 8) {
                            if isSaving { ProgressView().scaleEffect(0.7).tint(theme.bg) }
                            Text(isSaving ? "Saving…" : "Save Changes")
                        }
                    }
                    .buttonStyle(ThemedButtonStyle(variant: .accent, theme: theme, isDisabled: isSaving))
                    .disabled(isSaving)
                    .focusable(false)
                }
                .padding(.bottom, 40)
            }
            .padding(40)
            .frame(maxWidth: 700, alignment: .topLeading)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(theme.bg)
        .onChange(of: scrollToTop) { _, _ in
            withAnimation { proxy.scrollTo("top", anchor: .top) }
        }
        .task {
            await viewModel.loadConfig()
            populateFromConfig()
        }
        }
    }

    private func sectionTitle(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.system(size: 11, weight: .bold, design: .monospaced))
            .tracking(1.2)
            .foregroundColor(theme.muted)
    }

    private func labeledSecureField(_ label: String, text: Binding<String>, placeholder: String = "") -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label.uppercased()).font(theme.monoSmallFont).foregroundColor(theme.muted)
            ZStack(alignment: .leading) {
                if text.wrappedValue.isEmpty {
                    Text(placeholder)
                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                        .foregroundColor(theme.muted)
                        .padding(.leading, 8)
                        .allowsHitTesting(false)
                }
                SecureField("", text: text)
                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                    .foregroundColor(theme.text)
                    .textFieldStyle(.plain)
                    .padding(.leading, 8)
            }
            .padding(.vertical, 8)
            .background(theme.surface2)
            .border(theme.border, width: 1)
        }
    }

    private func labeledTextField(_ label: String, text: Binding<String>, placeholder: String = "", width: CGFloat? = nil) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label.uppercased()).font(theme.monoSmallFont).foregroundColor(theme.muted)
            TextField(placeholder, text: text)
                .font(.system(size: 13, weight: .semibold, design: .monospaced))
                .foregroundColor(theme.text)
                .frame(width: width)
                .padding(8)
                .background(theme.surface2)
                .border(theme.border, width: 1)
                .textFieldStyle(.plain)
        }
    }

    private func populateFromConfig() {
        guard let config = viewModel.currentConfig else { return }
        candidateName = config.profile.candidate.name
        candidateEmail = config.profile.candidate.email
        targetRole = config.profile.target_profile.role
        experienceYears = String(config.profile.target_profile.experience_years)
        experienceRange = config.profile.target_profile.experience_range
        noticePeriod = config.profile.target_profile.notice_period
        servingNotice = config.profile.target_profile.serving_notice
        coreSkills = config.profile.target_profile.core_skills.joined(separator: ", ")
        linkedinKeyword = config.profile.search.linkedin_keyword
        naukriKeyword = config.profile.search.naukri_keyword
        location = config.profile.search.location
        matchVariance = config.profile.filters.match_variance
        titleRedFlags = config.profile.filters.title.red_flags.joined(separator: ", ")
        excludedCompanies = config.profile.filters.company.excluded.filter { $0.lowercased() != config.profile.filters.company.current_employer.lowercased() }.joined(separator: ", ")
        currentEmployer = config.profile.filters.company.current_employer
        provider = config.providers.active_provider
        linkedinEmail = config.linkedin_email ?? ""
        naukriEmail = config.naukri_email ?? ""
    }

    private func saveSettings() {
        isSaving = true
        saveError = nil
        saveMessage = nil

        let payload = OnboardingPayload(
            candidate_name: candidateName,
            candidate_email: candidateEmail,
            target_role: targetRole,
            experience_years: Int(experienceYears) ?? 4,
            experience_range: experienceRange,
            notice_period: noticePeriod,
            serving_notice: servingNotice,
            core_skills: coreSkills.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty },
            linkedin_keyword: linkedinKeyword,
            naukri_keyword: naukriKeyword,
            location: location,
            match_variance: matchVariance,
            title_red_flags: titleRedFlags.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty },
            excluded_companies: excludedCompanies.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty },
            current_employer: currentEmployer,
            provider: provider,
            api_key: apiKey,
            linkedin_email: linkedinEmail,
            linkedin_password: linkedinPassword,
            naukri_email: naukriEmail,
            naukri_password: naukriPassword,
            analogous_skills: nil
        )

        viewModel.submitOnboarding(payload) { success, error in
            self.isSaving = false
            if success {
                self.saveMessage = "Settings saved. Changes take effect on the next pipeline run."
                self.scrollToTop.toggle()
            } else {
                self.saveError = error ?? "Failed to save settings"
            }
        }
    }
}


// MARK: - Main App Structure

struct ContentView: View {
    @StateObject var viewModel = PipelineViewModel()
    @State private var showOnboardingSheet = false
    let theme = AppTheme.default()

    var body: some View {
        HStack(spacing: 0) {
            SidebarView(viewModel: viewModel, theme: theme)
            Rectangle().fill(theme.border).frame(width: 1)
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    switch viewModel.page {
                    case "dashboard":
                        DashboardView(viewModel: viewModel, theme: theme)
                    case "schedule":
                        ScheduleView(viewModel: viewModel, theme: theme)
                    case "logs":
                        LogsView(viewModel: viewModel, theme: theme)
                    case "settings":
                        SettingsView(viewModel: viewModel, theme: theme)
                    default:
                        DashboardView(viewModel: viewModel, theme: theme)
                    }
                }
                .padding(40)
                .frame(maxWidth: 960, alignment: .topLeading)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .background(theme.bg)
            .overlay(
                Group {
                    if viewModel.backendStarting || !viewModel.onboardingCheckComplete {
                        ZStack {
                            theme.bg.opacity(0.92)
                            VStack(spacing: 16) {
                                ProgressView()
                                    .scaleEffect(1.2)
                                    .tint(theme.accent)
                                Text(viewModel.backendStarting ? "Starting pipeline engine…" : "Checking setup…")
                                    .font(theme.monoFont)
                                    .foregroundColor(theme.text)
                            }
                        }
                    }
                }
            )
        }
        .frame(minWidth: 900, minHeight: 650)
        .sheet(isPresented: $showOnboardingSheet) {
            OnboardingView(viewModel: viewModel, isPresented: $showOnboardingSheet, theme: theme)
        }
        .task {
            await viewModel.prepareBackend()
            presentOnboardingIfNeeded()
        }
        .onChange(of: viewModel.onboardingConfigured) { _, _ in
            if viewModel.onboardingCheckComplete && !viewModel.onboardingConfigured {
                showOnboardingSheet = true
            }
        }
    }

    private func presentOnboardingIfNeeded() {
        if viewModel.onboardingCheckComplete && !viewModel.onboardingConfigured {
            showOnboardingSheet = true
        }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationWillTerminate(_ notification: Notification) {
        // Shut down the backend only if:
        //   1. We started it ourselves, AND
        //   2. No pipeline is currently running.
        // If a pipeline is running (whether started by us or pre-existing), leave
        // the backend alive so the run can complete and write its final state.
        let manager = BackendManager.shared
        if !manager.isAlreadyRunning, manager.pipelineWasRunningAtLaunch == false {
            let reachable = manager.backendIsReachableNow()
            if reachable {
                let running = manager.pipelineIsRunningNow()
                if !running {
                    manager.stopServer()
                }
            }
        }
    }
}

struct AiAutomationApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowStyle(.hiddenTitleBar)
        .windowToolbarStyle(.unifiedCompact)
    }
}

// Entry point is in mac/main.swift: AiAutomationApp.main()
