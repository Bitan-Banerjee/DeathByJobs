import SwiftUI
import AppKit
import Foundation
import Combine

// MARK: - Core Design System & Theme

/// Halftone/Dither pattern view for the vintage theme
struct HalftonePattern: View {
    let color: Color
    let density: CGFloat // 0.0 (sparse) to 1.0 (dense)
    
    var body: some View {
        Canvas { context, size in
            let dotSize = 1.5
            let spacing = max(1.5, (1.0 - density) * 8.0)
            
            let numCols = Int(size.width / (dotSize + spacing))
            let numRows = Int(size.height / (dotSize + spacing))
            
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

// The unified theme object
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

    static func from() -> AppTheme {
        return AppTheme(
            name: "vintage",
            bg: Color(hex: "F5F0E6"),
            surface: Color(hex: "F5F0E6"),
            surface2: Color(hex: "EAE5D9"),
            border: Color(hex: "0D0D0D"),
            text: Color(hex: "0D0D0D"),
            muted: Color(hex: "5A5A5A"),
            accent: Color(hex: "A67B84"),
            accentBg: Color(hex: "A67B84"),
            accentDim: Color(hex: "A67B84").opacity(0.7),
            errorRed: Color(hex: "990000"),
            errorRedBg: Color(hex: "990000").opacity(0.15),
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

// MARK: - Models
struct PipelineParams: Codable { var jobs: Int; var target: Int; var max_loops: Int; var mode: String }
struct StatusResponse: Codable { let status: String; let pid: Int? }
struct CronJob: Codable, Identifiable, Equatable { let id: String; let name: String; let enabled: Bool; let minute: Int; let hour: Int }
struct CronResponse: Codable { let jobs: [CronJob]; }
struct LogsResponse: Codable { let lines: [String]? }

// MARK: - Backend Process Manager
class BackendManager {
    static let shared = BackendManager()
    private var process: Process?
    private let projectRoot = "/Users/bitanbanerjee/Coding/GitHub_Repos/AiAutomation"
    func startServer() {
        killPort8000()
        let pythonPath = findPythonPath()
        let p = Process(); p.executableURL = URL(fileURLWithPath: pythonPath); p.currentDirectoryURL = URL(fileURLWithPath: projectRoot)
        let pythonCmd = "import sys, uvicorn; sys.path.insert(0, '\(projectRoot)'); uvicorn.run('src.api.main:app', host='127.0.0.1', port=8000, log_level='warning')"
        p.arguments = ["-u", "-c", pythonCmd]
        let logDir = "\(projectRoot)/logs"; try? FileManager.default.createDirectory(atPath: logDir, withIntermediateDirectories: true)
        let logPath = "\(logDir)/app_launch.log"; FileManager.default.createFile(atPath: logPath, contents: nil)
        if let fileHandle = FileHandle(forWritingAtPath: logPath) { p.standardOutput = fileHandle; p.standardError = fileHandle }
        self.process = p; do { try p.run() } catch { print("Native App Error: Failed to start FastAPI server: \(error)") }
    }
    func stopServer() { if let p = process, p.isRunning { p.terminate(); p.waitUntilExit() }; killPort8000() }
    private func killPort8000() { let sh = Process(); sh.executableURL = URL(fileURLWithPath: "/bin/sh"); sh.arguments = ["-c", "lsof -ti :8000 | xargs kill -9 2>/dev/null || true"]; try? sh.run(); sh.waitUntilExit() }
    private func findPythonPath() -> String {
        let customPath = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12"
        if FileManager.default.fileExists(atPath: customPath) { return customPath }
        let commonPaths = ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]
        for path in commonPaths { if FileManager.default.fileExists(atPath: path) { return path } }
        return "python3"
    }
}

// MARK: - View Model
class PipelineViewModel: ObservableObject {
    @Published var status: String = "idle"
    @Published var logs: [String] = []
    @Published var cronJobs: [CronJob] = []
    @Published var activeStage: Int = -1
    @Published var page: String = "dashboard"
    @Published var jobs: Int = 25
    @Published var target: Int = 50
    @Published var maxLoops: Int = 4
    @Published var mode: String = "quota"
    private var cancellables = Set<AnyCancellable>()
    private let baseUrl = "http://127.0.0.1:8000"
    init() { startPolling() }
    func startPolling() { /* ... */ }
    func refreshAll() { /* ... */ }
    func refreshStatusAndLogs() { /* ... */ }
    func refreshCron() { /* ... */ }
    func fetchStatus() async { /* ... */ }
    func fetchLogs() async { /* ... */ }
    func fetchCron() async { /* ... */ }
    func startPipeline() {
        guard let url = URL(string: "\(baseUrl)/start_job") else {
            print("Invalid URL for start_job")
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        let task = URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            if let error = error {
                print("Error starting pipeline: \(error.localizedDescription)")
                DispatchQueue.main.async {
                    self?.status = "error"
                }
                return
            }
            
            // On completion, immediately refresh status to reflect the new state
            DispatchQueue.main.async {
                self?.refreshStatusAndLogs()
            }
        }
        task.resume()
    }
    func stopPipeline() { /* ... */ }
    func updateCron(jobId: String, enabled: Bool?, hour: Int?, minute: Int?) { /* ... */ }
    private func updateActiveStage() { /* ... */ }
}

// MARK: - THEMED COMPONENTS
struct ThemedCard<Content: View>: View {
    let theme: AppTheme
    var borderColor: Color? = nil
    let content: Content
    
    init(theme: AppTheme, borderColor: Color? = nil, @ViewBuilder content: () -> Content) {
        self.theme = theme; self.borderColor = borderColor; self.content = content()
    }
    var body: some View { content.padding(24).background(theme.surface).border(borderColor ?? theme.border, width: 1) }
}

struct ThemedButtonStyle: ButtonStyle {
    let variant: ButtonVariant
    let theme: AppTheme
    let isDisabled: Bool
    enum ButtonVariant { case accent, red, ghost, saveSmall }
    
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: variant == .saveSmall ? 11 : 13, weight: .semibold, design: .monospaced))
            .foregroundColor(foreground(isPressed: configuration.isPressed))
            .padding(.horizontal, variant == .saveSmall ? 12 : 18)
            .padding(.vertical, variant == .saveSmall ? 4 : 9)
            .background(background(isPressed: configuration.isPressed))
            .border(border(isPressed: configuration.isPressed), width: 1)
            .opacity(isDisabled ? 0.5 : (configuration.isPressed ? 0.82 : 1.0))
            .scaleEffect(configuration.isPressed && !isDisabled ? 0.97 : 1.0)
    }
    private func foreground(isPressed: Bool) -> Color {
        return variant == .accent ? theme.bg : theme.text
    }
    private func background(isPressed: Bool) -> Color {
        switch variant {
        case .accent: return theme.accent
        case .red: return theme.errorRedBg
        default: return theme.surface2
        }
    }
    private func border(isPressed: Bool) -> Color {
        switch variant {
        case .accent: return theme.accent
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
                Rectangle().fill(isOn ? theme.accentBg : theme.surface2).frame(width: 42, height: 24).border(isOn ? theme.accentDim : theme.border, width: 2)
                Rectangle().fill(isOn ? theme.accent : theme.muted).frame(width: 16, height: 16).padding(.horizontal, 2)
            }
        }.buttonStyle(.plain)
    }
}

// MARK: - Rebuilt Original Views
struct LogoView: View {
    var body: some View {
        ZStack {
            Rectangle().fill(Color.primary.opacity(0.1)).frame(width: 32, height: 32)
            HStack(spacing: 2) {
                Text(">").font(.system(size: 16, weight: .bold, design: .monospaced))
                Rectangle().fill(Color.primary).frame(width: 6, height: 3).offset(y: 4)
            }.foregroundColor(.primary)
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
        }.frame(maxWidth: .infinity).padding(.vertical, 8).background(pillBg).foregroundColor(pillFg).border(pillBorder, width: 2)
    }
    private var dotColor: Color { switch status.lowercased() { case "running": return theme.accent; case "error": return theme.errorRed; default: return theme.muted } }
    private var pillBg: Color { switch status.lowercased() { case "running": return theme.accentBg; case "error": return theme.errorRedBg; default: return theme.surface2 } }
    private var pillFg: Color { switch status.lowercased() { case "running": return theme.accent; case "error": return theme.errorRed; default: return theme.muted } }
    private var pillBorder: Color { switch status.lowercased() { case "running": return theme.accent; case "error": return theme.errorRed; default: return theme.border } }
}

struct StatBoxView: View {
    let label: String, value: String, isAccent: Bool, theme: AppTheme
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(label.uppercased()).font(theme.monoSmallFont).tracking(1.0).foregroundColor(theme.muted)
            Text(value).font(theme.monoLargeFont).foregroundColor(isAccent ? theme.accent : theme.text).lineLimit(1)
        }.frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 16).padding(.vertical, 18).background(theme.surface).border(theme.border, width: 2)
    }
}

struct StageNodeView: View {
    let label: String, iconName: String, isActive: Bool, isDone: Bool, theme: AppTheme
    var body: some View {
        VStack(spacing: 10) {
            ZStack {
                Rectangle().fill(isActive || isDone ? theme.accentBg : theme.surface)
                    .frame(width: 52, height: 52)
                    .border(theme.border, width: 1)
                if isActive || isDone {
                    HalftonePattern(color: theme.text.opacity(0.4), density: 0.4)
                }
                Image(systemName: iconName).font(.system(size: 20)).foregroundColor(isActive || isDone ? theme.bg : theme.muted)
            }
            Text(label.uppercased()).font(.system(size: 9, weight: .bold, design: .monospaced)).tracking(0.8)
                .foregroundColor(isActive || isDone ? theme.text : theme.muted)
                .multilineTextAlignment(.center)
        }
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
    var body: some View { Text(line.isEmpty ? " " : line).font(.system(size: 11, design: .monospaced)).foregroundColor(textColor).lineLimit(nil).fixedSize(horizontal: false, vertical: true).frame(maxWidth: .infinity, alignment: .leading) }
    private var textColor: Color {
        if line.contains("FAILURE") { return theme.errorRed }
        if line.contains("✅") { return theme.accent }
        return theme.text
    }
}

struct CronRowView: View {
    let job: CronJob, theme: AppTheme, onUpdate: (Bool?, Int?, Int?) -> Void
    @State private var hourStr: String
    @State private var minuteStr: String
    
    init(job: CronJob, theme: AppTheme, onUpdate: @escaping (Bool?, Int?, Int?) -> Void) {
        self.job = job; self.theme = theme; self.onUpdate = onUpdate
        _hourStr = State(initialValue: String(format: "%02d", job.hour))
        _minuteStr = State(initialValue: String(format: "%02d", job.minute))
    }
    
    var body: some View {
        HStack(spacing: 16) {
            ThemedToggle(isOn: Binding(get: { job.enabled }, set: { onUpdate($0, nil, nil) }), theme: theme)
            VStack(alignment: .leading, spacing: 3) {
                Text(job.name).font(.system(size: 14, weight: .semibold, design: .monospaced)).foregroundColor(theme.text)
                Text(job.enabled ? "Runs daily at \(hourStr):\(minuteStr)" : "Disabled").font(.system(size: 11, design: .monospaced)).foregroundColor(theme.muted)
            }
            Spacer()
            HStack(spacing: 6) {
                TextField("", text: $hourStr).font(.system(size: 13, design: .monospaced)).multilineTextAlignment(.center).padding(4).background(theme.surface).border(theme.border, width: 2).frame(width: 56).textFieldStyle(.plain)
                Text(":").font(.system(size: 13, weight: .bold, design: .monospaced)).foregroundColor(theme.muted)
                TextField("", text: $minuteStr).font(.system(size: 13, design: .monospaced)).multilineTextAlignment(.center).padding(4).background(theme.surface).border(theme.border, width: 2).frame(width: 56).textFieldStyle(.plain)
                if isDirty { Button("Save") { if let h = Int(hourStr), let m = Int(minuteStr) { onUpdate(nil, h, m) } }.buttonStyle(ThemedButtonStyle(variant: .saveSmall, theme: theme, isDisabled: false)) }
            }
        }.padding(.vertical, 16).overlay(Rectangle().frame(height: 1).foregroundColor(theme.border), alignment: .bottom)
    }
    private var isDirty: Bool { hourStr != String(format: "%02d", job.hour) || minuteStr != String(format: "%02d", job.minute) }
}

// MARK: - Pages
struct SidebarView: View {
    @ObservedObject var viewModel: PipelineViewModel
    let theme: AppTheme
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) { LogoView(); Text("AI-PIPELINE").font(.system(size: 16, weight: .bold, design: .monospaced)).tracking(0.8).foregroundColor(theme.text) }.padding([.horizontal, .top], 24).padding(.bottom, 32)
            VStack(spacing: 2) {
                Button(action: { viewModel.page = "dashboard" }) { HStack(spacing: 10) { Image(systemName: "square.grid.2x2.fill"); Text("Dashboard") } }.buttonStyle(SidebarButtonStyle(isActive: viewModel.page == "dashboard", theme: theme))
                Button(action: { viewModel.page = "schedule" }) { HStack(spacing: 10) { Image(systemName: "calendar"); Text("Schedule") } }.buttonStyle(SidebarButtonStyle(isActive: viewModel.page == "schedule", theme: theme))
                Button(action: { viewModel.page = "logs" }) { HStack(spacing: 10) { Image(systemName: "doc.text"); Text("Logs") } }.buttonStyle(SidebarButtonStyle(isActive: viewModel.page == "logs", theme: theme))
            }.padding(.horizontal, 12)
            Spacer()
            VStack(spacing: 12) {
                StatusPillView(status: viewModel.status, theme: theme)
            }.padding(.horizontal, 24).padding(.top, 20).border(theme.border, width: 1).padding(.bottom, 24)
        }.frame(width: 220).background(theme.bg)
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
                    if isActive {
                        HalftonePattern(color: theme.text.opacity(0.8), density: 0.5)
                    } else if configuration.isPressed {
                        theme.surface2
                    } else {
                        Color.clear
                    }
                }
            )
            .border(isActive ? theme.border : Color.clear, width: 1)
            .contentShape(Rectangle())
    }
}

struct DashboardView: View {
    @ObservedObject var viewModel: PipelineViewModel
    let theme: AppTheme
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Dashboard").font(theme.headingFont).foregroundColor(theme.text)
                Text("Monitor and control your job automation pipeline").font(theme.monoFont).foregroundColor(theme.muted)
            }.padding(.bottom, 36)
            if viewModel.status == "error" {
                ThemedCard(theme: theme, borderColor: theme.errorRed) { Text("CONNECTION ERROR...") }.padding(.bottom, 20)
            }
            HStack(spacing: 14) {
                StatBoxView(label: "Target Today", value: "\(viewModel.target)", isAccent: true, theme: theme)
                StatBoxView(label: "Max Loops", value: "\(viewModel.maxLoops)", isAccent: false, theme: theme)
                StatBoxView(label: "Pipeline", value: viewModel.status, isAccent: viewModel.status == "running", theme: theme)
            }.padding(.bottom, 20)
            ThemedCard(theme: theme) {
                VStack(alignment: .leading, spacing: 24) {
                    Text("Pipeline Stages").font(.system(size: 11, weight: .bold, design: .monospaced)).tracking(1.2).foregroundColor(theme.muted)
                    HStack(spacing: 0) {
                        StageNodeView(label: "Scrape", iconName: "globe", isActive: viewModel.status == "running" && viewModel.activeStage == 0, isDone: viewModel.activeStage > 0, theme: theme)
                        StageLineView(isDone: viewModel.activeStage > 0, theme: theme)
                        StageNodeView(label: "AI Filter", iconName: "line.3.horizontal.decrease", isActive: viewModel.status == "running" && viewModel.activeStage == 1, isDone: viewModel.activeStage > 1, theme: theme)
                        StageLineView(isDone: viewModel.activeStage > 1, theme: theme)
                        StageNodeView(label: "Tailor", iconName: "pencil.and.outline", isActive: viewModel.status == "running" && viewModel.activeStage == 2, isDone: viewModel.activeStage > 2, theme: theme)
                        StageLineView(isDone: viewModel.activeStage > 2, theme: theme)
                        StageNodeView(label: "Apply", iconName: "paperplane.fill", isActive: viewModel.status == "running" && viewModel.activeStage == 3, isDone: viewModel.activeStage > 3, theme: theme)
                        StageLineView(isDone: viewModel.activeStage > 3, theme: theme)
                        StageNodeView(label: "Export", iconName: "square.and.arrow.down", isActive: viewModel.status == "running" && viewModel.activeStage == 4, isDone: viewModel.activeStage > 4, theme: theme)
                    }.padding(.horizontal, 10)
                }
            }.padding(.bottom, 20)
            ThemedCard(theme: theme) {
                 VStack(alignment: .leading, spacing: 24) {
                    Text("Run Pipeline")
                        .font(.system(size: 11, weight: .bold, design: .monospaced))
                        .tracking(1.2)
                        .foregroundColor(theme.muted)
                    HStack(spacing: 10) {
                        Button(action: { viewModel.startPipeline() }) { HStack(spacing: 7) { Image(systemName: "play.fill"); Text("Start") } }
                        .buttonStyle(ThemedButtonStyle(variant: .accent, theme: theme, isDisabled: viewModel.status == "running"))
                        .disabled(viewModel.status == "running")
                        
                        Button(action: { viewModel.stopPipeline() }) { HStack(spacing: 7) { Image(systemName: "stop.fill"); Text("Stop") } }
                        .buttonStyle(ThemedButtonStyle(variant: .red, theme: theme, isDisabled: viewModel.status != "running"))
                        .disabled(viewModel.status != "running")
                    }
                }
            }
        }
    }
}

// MARK: - Main App Structure
struct ContentView: View {
    @StateObject var viewModel = PipelineViewModel()
    
    var body: some View {
        let theme = AppTheme.from()
        HStack(spacing: 0) {
            SidebarView(viewModel: viewModel, theme: theme)
            Rectangle().fill(theme.border).frame(width: 1)
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    if viewModel.page == "dashboard" {
                        DashboardView(viewModel: viewModel, theme: theme)
                    } else {
                        // Placeholder for other views
                        Text("\(viewModel.page) View").font(theme.headingFont)
                    }
                }
                .padding(40).frame(maxWidth: 860, alignment: .topLeading)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .background(theme.bg)
        }
        .frame(minWidth: 900, minHeight: 650)
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) { BackendManager.shared.startServer() }
    func applicationWillTerminate(_ notification: Notification) { BackendManager.shared.stopServer() }
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
