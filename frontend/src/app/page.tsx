"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  UploadCloud, 
  FileText, 
  Sparkles, 
  BookOpen, 
  Music, 
  Trash2, 
  Loader2, 
  Check, 
  FileUp, 
  ChevronRight,
  AlertTriangle
} from "lucide-react";

// API Base URL - configure fallback to localhost
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Segment {
  type: "dialogue" | "narration";
  text: string;
  emotion: string;
  color: string;
}

interface Character {
  name: string;
  mentions: number;
  voice_profile: string;
}

interface AnnotatedContent {
  preprocessed_text: string;
  segments: Segment[];
  characters: Character[];
  emotion_summary: Record<string, number>;
}

interface Story {
  id: number;
  title: string;
  content: string;
  nlp_status?: "pending" | "processing" | "completed" | "failed";
  annotated_content?: AnnotatedContent | null;
  created_at: string;
}

export default function Home() {
  // Tabs & Form State
  const [activeTab, setActiveTab] = useState<"write" | "upload">("write");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  
  // App States
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [stories, setStories] = useState<Story[]>([]);
  const [isLoadingStories, setIsLoadingStories] = useState(false);
  const [selectedStory, setSelectedStory] = useState<Story | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch stories on load
  const fetchStories = async (updatedSelectedId?: number) => {
    setIsLoadingStories(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/stories`);
      if (res.ok) {
        const data = await res.json();
        setStories(data);
        
        // Keep selected story up to date
        const idToFind = updatedSelectedId || selectedStory?.id;
        if (idToFind) {
          const updated = data.find((s: Story) => s.id === idToFind);
          if (updated) {
            setSelectedStory(updated);
          }
        } else if (data.length > 0) {
          setSelectedStory(data[0]);
        }
      }
    } catch (err) {
      console.error("Failed to fetch stories:", err);
    } finally {
      setIsLoadingStories(false);
    }
  };

  // Poll analysis status
  const pollAnalysis = async (storyId: number) => {
    let attempts = 0;
    const maxAttempts = 30; // 30 attempts (45 seconds)
    
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await fetch(`${API_BASE_URL}/api/stories/${storyId}/analysis`);
        if (res.ok) {
          const data = await res.json();
          if (data.nlp_status === "completed" || data.nlp_status === "failed") {
            clearInterval(interval);
            setIsAnalyzing(false);
            fetchStories(storyId);
            if (data.nlp_status === "completed") {
              setSuccessMessage("NLP analysis completed successfully!");
            } else {
              setErrorMessage("NLP analysis failed.");
            }
          }
        }
      } catch (err) {
        console.error("Error polling analysis:", err);
      }
      
      if (attempts >= maxAttempts) {
        clearInterval(interval);
        setIsAnalyzing(false);
        setErrorMessage("Analysis timed out. Please try again.");
      }
    }, 1500);
  };

  // Handle triggering NLP pipeline
  const handleAnalyzeStory = async (storyId: number) => {
    setIsAnalyzing(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/stories/${storyId}/analyze`, {
        method: "POST",
      });
      
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to trigger analysis");
      }
      
      // Update local state to show processing immediately
      if (selectedStory && selectedStory.id === storyId) {
        setSelectedStory({
          ...selectedStory,
          nlp_status: "processing"
        });
      }
      
      // Start polling
      pollAnalysis(storyId);
    } catch (err: any) {
      setErrorMessage(err.message || "An error occurred while triggering analysis.");
      setIsAnalyzing(false);
    }
  };

  useEffect(() => {
    fetchStories();
  }, []);

  // Handle manual story submission
  const handleSubmitStory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !content.trim()) {
      setErrorMessage("Please provide both a title and story content.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    const formData = new FormData();
    formData.append("title", title);
    formData.append("content", content);

    try {
      const res = await fetch(`${API_BASE_URL}/api/stories`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to create story");
      }

      const newStory = await res.json();
      setSuccessMessage("Story created successfully!");
      setTitle("");
      setContent("");
      setSelectedStory(newStory);
      fetchStories();
    } catch (err: any) {
      setErrorMessage(err.message || "An error occurred while creating the story.");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle document upload
  const handleUploadStory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMessage("Please select a file to upload.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    const formData = new FormData();
    formData.append("file", selectedFile);
    if (title.trim()) {
      formData.append("title", title);
    }

    try {
      const res = await fetch(`${API_BASE_URL}/api/stories/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to upload and parse file");
      }

      const newStory = await res.json();
      setSuccessMessage(`File parsed and story "${newStory.title}" saved!`);
      setTitle("");
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setSelectedStory(newStory);
      fetchStories();
    } catch (err: any) {
      setErrorMessage(err.message || "An error occurred while parsing the document.");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      const ext = file.name.split(".").pop()?.toLowerCase();
      if (["pdf", "docx", "doc", "txt"].includes(ext || "")) {
        setSelectedFile(file);
        setErrorMessage(null);
      } else {
        setErrorMessage("Unsupported file type. Please upload a PDF, DOCX, or TXT file.");
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0B0F] text-zinc-100 flex flex-col font-sans selection:bg-[#7C5CFF]/30 selection:text-white">
      {/* Background glow effects */}
      <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-[#7C5CFF]/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-10 right-1/4 w-[400px] h-[400px] bg-[#00D4FF]/5 rounded-full blur-[100px] pointer-events-none" />

      {/* Top Header */}
      <header className="border-b border-[#1E1E2A] bg-[#0B0B0F]/80 backdrop-blur-md sticky top-0 z-50 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3 group">
            <div className="p-2.5 bg-gradient-to-tr from-[#7C5CFF] to-[#00D4FF] rounded-xl shadow-lg shadow-[#7C5CFF]/20 group-hover:scale-105 transition-transform duration-300">
              <Music className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-xl tracking-tight bg-gradient-to-r from-white via-zinc-100 to-zinc-400 bg-clip-text text-transparent">
                StoryVoice <span className="text-[#7C5CFF]">AI</span>
              </h1>
              <p className="text-[10px] text-zinc-500 font-medium uppercase tracking-wider">Multi-Voice Story Generation</p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-xs bg-[#12121A] border border-[#1E1E2A] px-3 py-1.5 rounded-full text-zinc-400 flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>Local Pipeline Running</span>
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:py-10 grid grid-cols-1 lg:grid-cols-12 gap-8 z-10">
        
        {/* Left Side: Create / Import Story (8 cols on desktop) */}
        <section className="lg:col-span-7 flex flex-col space-y-6">
          <div className="space-y-2">
            <h2 className="text-3xl font-bold tracking-tight text-white flex items-center gap-2">
              Generate Audiobooks <Sparkles className="w-6 h-6 text-[#A78BFA] animate-pulse" />
            </h2>
            <p className="text-zinc-400 text-sm md:text-base">
              Enter your story or upload a document to analyze emotional tones and render character-specific narrations.
            </p>
          </div>

          {/* Form Card */}
          <div className="bg-[#12121A] border border-[#1E1E2A] rounded-2xl p-6 shadow-2xl relative overflow-hidden transition-all duration-300 hover:border-[#7C5CFF]/20">
            {/* Glow Border Effect */}
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-[#7C5CFF] via-[#A78BFA] to-[#00D4FF]" />
            
            {/* Tab Selectors */}
            <div className="flex border-b border-[#1E1E2A] mb-6">
              <button
                type="button"
                onClick={() => { setActiveTab("write"); setErrorMessage(null); }}
                className={`pb-3 px-4 font-semibold text-sm transition-all relative ${
                  activeTab === "write" 
                    ? "text-[#7C5CFF]" 
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                Write / Paste Content
                {activeTab === "write" && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#7C5CFF]" />
                )}
              </button>
              <button
                type="button"
                onClick={() => { setActiveTab("upload"); setErrorMessage(null); }}
                className={`pb-3 px-4 font-semibold text-sm transition-all relative ${
                  activeTab === "upload" 
                    ? "text-[#7C5CFF]" 
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                Upload File (PDF/DOCX/TXT)
                {activeTab === "upload" && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#7C5CFF]" />
                )}
              </button>
            </div>

            {/* Error & Success Messages */}
            {errorMessage && (
              <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded-xl flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}
            {successMessage && (
              <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs rounded-xl flex items-center space-x-2">
                <Check className="w-4 h-4 shrink-0" />
                <span>{successMessage}</span>
              </div>
            )}

            {/* Forms */}
            {activeTab === "write" ? (
              <form onSubmit={handleSubmitStory} className="space-y-4">
                <div className="space-y-1.5">
                  <label htmlFor="write-title" className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Story Title</label>
                  <input
                    id="write-title"
                    type="text"
                    placeholder="Enter the title of your story..."
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    disabled={isSubmitting}
                    className="w-full bg-[#0B0B0F] border border-[#1E1E2A] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#7C5CFF] focus:ring-1 focus:ring-[#7C5CFF] text-zinc-100 placeholder-zinc-600 transition-all duration-200"
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="write-content" className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Story Content</label>
                  <textarea
                    id="write-content"
                    placeholder="Paste or write your story paragraphs here. Use quotation marks for dialogues to help the AI detect characters..."
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    disabled={isSubmitting}
                    rows={8}
                    className="w-full bg-[#0B0B0F] border border-[#1E1E2A] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#7C5CFF] focus:ring-1 focus:ring-[#7C5CFF] text-zinc-100 placeholder-zinc-600 transition-all duration-200 resize-y min-h-[160px]"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full bg-gradient-to-r from-[#7C5CFF] to-[#A78BFA] hover:from-[#6b4ae6] hover:to-[#9675e8] active:scale-[0.98] text-white font-semibold py-3 rounded-xl transition-all duration-200 shadow-lg shadow-[#7C5CFF]/20 flex items-center justify-center space-x-2 disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Creating Story...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5" />
                      <span>Save and Extract Story</span>
                    </>
                  )}
                </button>
              </form>
            ) : (
              <form onSubmit={handleUploadStory} className="space-y-4">
                <div className="space-y-1.5">
                  <label htmlFor="upload-title" className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Story Title (Optional)</label>
                  <input
                    id="upload-title"
                    type="text"
                    placeholder="Determined from file name if left blank..."
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    disabled={isSubmitting}
                    className="w-full bg-[#0B0B0F] border border-[#1E1E2A] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#7C5CFF] focus:ring-1 focus:ring-[#7C5CFF] text-zinc-100 placeholder-zinc-600 transition-all duration-200"
                  />
                </div>
                
                {/* Drag and Drop Dropzone */}
                <div className="space-y-1.5">
                  <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Upload Document</span>
                  <div
                    onClick={() => !isSubmitting && fileInputRef.current?.click()}
                    className={`w-full border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all duration-200 ${
                      selectedFile 
                        ? "border-[#7C5CFF]/70 bg-[#7C5CFF]/5" 
                        : "border-[#1E1E2A] bg-[#0B0B0F] hover:border-[#7C5CFF]/40"
                    } ${isSubmitting ? "opacity-50 pointer-events-none" : ""}`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,.docx,.doc,.txt"
                      onChange={handleFileChange}
                      className="hidden"
                    />
                    
                    {selectedFile ? (
                      <div className="text-center space-y-2">
                        <div className="mx-auto w-12 h-12 rounded-full bg-[#7C5CFF]/15 flex items-center justify-center text-[#7C5CFF] animate-bounce">
                          <FileUp className="w-6 h-6" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-zinc-200 truncate max-w-[300px]">
                            {selectedFile.name}
                          </p>
                          <p className="text-xs text-zinc-500">
                            {(selectedFile.size / 1024).toFixed(1)} KB
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedFile(null);
                            if (fileInputRef.current) fileInputRef.current.value = "";
                          }}
                          className="text-xs text-red-400 hover:text-red-300 font-medium underline inline-flex items-center space-x-1"
                        >
                          <Trash2 className="w-3 h-3" />
                          <span>Remove</span>
                        </button>
                      </div>
                    ) : (
                      <div className="text-center space-y-3">
                        <div className="mx-auto w-12 h-12 rounded-full bg-[#1E1E2A] flex items-center justify-center text-zinc-400">
                          <UploadCloud className="w-6 h-6" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-zinc-300">
                            Drag & drop your file or <span className="text-[#7C5CFF] underline">browse</span>
                          </p>
                          <p className="text-xs text-zinc-500 mt-1">
                            Supports PDF, DOCX, and TXT (Max 10MB)
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting || !selectedFile}
                  className="w-full bg-gradient-to-r from-[#7C5CFF] to-[#00D4FF] hover:from-[#6b4ae6] hover:to-[#00b2d6] active:scale-[0.98] text-white font-semibold py-3 rounded-xl transition-all duration-200 shadow-lg shadow-[#7C5CFF]/20 flex items-center justify-center space-x-2 disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Parsing & Importing Document...</span>
                    </>
                  ) : (
                    <>
                      <FileText className="w-5 h-5" />
                      <span>Parse and Load Story</span>
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </section>

        {/* Right Side: Saved Stories & Story Preview (5 cols on desktop) */}
        <section className="lg:col-span-5 flex flex-col space-y-6">
          <div className="space-y-2">
            <h3 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-[#7C5CFF]" /> Saved Stories
            </h3>
            <p className="text-zinc-500 text-xs">
              Select an uploaded story from your local library to view details and parsed content.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6">
            {/* Story List Card */}
            <div className="bg-[#12121A] border border-[#1E1E2A] rounded-2xl p-4 shadow-xl max-h-[300px] overflow-y-auto custom-scrollbar">
              {isLoadingStories ? (
                <div className="py-12 flex flex-col items-center justify-center text-zinc-500 space-y-2 text-sm">
                  <Loader2 className="w-6 h-6 animate-spin text-[#7C5CFF]" />
                  <span>Loading library...</span>
                </div>
              ) : stories.length === 0 ? (
                <div className="py-12 text-center text-zinc-500 text-sm">
                  <BookOpen className="w-8 h-8 mx-auto mb-2 text-zinc-600 opacity-60" />
                  <span>Your library is empty. Upload your first story!</span>
                </div>
              ) : (
                <div className="space-y-1.5">
                  {stories.map((story) => (
                    <button
                      key={story.id}
                      onClick={() => setSelectedStory(story)}
                      className={`w-full text-left p-3 rounded-xl transition-all duration-200 flex items-center justify-between group ${
                        selectedStory?.id === story.id 
                          ? "bg-[#7C5CFF]/10 border border-[#7C5CFF]/30 text-white" 
                          : "border border-transparent text-zinc-400 hover:bg-[#1A1A24] hover:text-zinc-200"
                      }`}
                    >
                      <div className="truncate pr-4 flex-1">
                        <p className="font-semibold text-sm truncate">{story.title}</p>
                        <p className="text-[10px] text-zinc-500 mt-0.5">
                          {new Date(story.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit"
                          })}
                        </p>
                      </div>
                      <ChevronRight className={`w-4 h-4 shrink-0 transition-transform ${
                        selectedStory?.id === story.id 
                          ? "text-[#7C5CFF] translate-x-1" 
                          : "text-zinc-600 group-hover:text-zinc-400 group-hover:translate-x-0.5"
                      }`} />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Selected Story Preview */}
            <div className="bg-[#12121A] border border-[#1E1E2A] rounded-2xl p-6 shadow-xl flex-1 flex flex-col min-h-[350px]">
              {selectedStory ? (
                <div className="flex flex-col h-full space-y-4">
                  <div className="border-b border-[#1E1E2A] pb-3 flex justify-between items-start">
                    <div>
                      <h4 className="font-bold text-base text-zinc-100">{selectedStory.title}</h4>
                      <p className="text-[10px] text-zinc-500 mt-1 uppercase tracking-wider">
                        {selectedStory.nlp_status === "completed" 
                          ? `Analyzed Story (${selectedStory.content.length} characters)` 
                          : `Extracted text (${selectedStory.content.length} characters)`}
                      </p>
                    </div>
                    {selectedStory.nlp_status && (
                      <span className={`text-[10px] font-semibold uppercase px-2.5 py-1 rounded-full border ${
                        selectedStory.nlp_status === "completed"
                          ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                          : selectedStory.nlp_status === "processing"
                          ? "bg-amber-500/10 border-amber-500/30 text-amber-400 animate-pulse"
                          : selectedStory.nlp_status === "failed"
                          ? "bg-red-500/10 border-red-500/30 text-red-400"
                          : "bg-zinc-500/10 border-zinc-500/30 text-zinc-400"
                      }`}>
                        {selectedStory.nlp_status}
                      </span>
                    )}
                  </div>

                  {selectedStory.nlp_status === "processing" ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-center py-12 space-y-4">
                      <Loader2 className="w-8 h-8 animate-spin text-[#7C5CFF]" />
                      <div className="space-y-1">
                        <p className="text-sm font-semibold text-zinc-200">Analyzing Story Content</p>
                        <p className="text-xs text-zinc-500 max-w-[280px] mx-auto">
                          Running NLP pipeline to extract characters, segments, and emotional tones...
                        </p>
                      </div>
                    </div>
                  ) : selectedStory.nlp_status === "completed" && selectedStory.annotated_content ? (
                    <div className="flex-1 flex flex-col space-y-4 min-h-0">
                      {/* Character Lists */}
                      {selectedStory.annotated_content.characters && selectedStory.annotated_content.characters.length > 0 ? (
                        <div className="space-y-1.5">
                          <h5 className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">Detected Characters & Voices</h5>
                          <div className="flex flex-wrap gap-1.5">
                            {selectedStory.annotated_content.characters.map((char) => (
                              <span key={char.name} className="px-2.5 py-1 bg-[#1A1A24] border border-[#1E1E2A] text-zinc-300 rounded-lg text-xs font-medium flex items-center space-x-1.5 hover:border-[#7C5CFF]/30 transition-colors">
                                <span className="w-1.5 h-1.5 rounded-full bg-[#7C5CFF]" />
                                <span>{char.name}</span>
                                <span className="text-[10px] text-zinc-500">({char.voice_profile})</span>
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="p-2.5 bg-[#1A1A24]/50 border border-[#1E1E2A] rounded-xl text-[11px] text-zinc-500">
                          No characters detected in this story.
                        </div>
                      )}

                      {/* Annotated Content Blocks */}
                      <div className="flex-1 overflow-y-auto max-h-[260px] text-sm text-zinc-300 leading-relaxed bg-[#0B0B0F] p-4 rounded-xl border border-[#1E1E2A] custom-scrollbar space-y-2 select-text">
                        {selectedStory.annotated_content.segments.map((seg, idx) => (
                          <span 
                            key={idx} 
                            className={`inline px-1 py-0.5 rounded transition-all duration-200 cursor-help ${
                              seg.type === "dialogue" ? "font-semibold border-b border-dashed border-zinc-700" : ""
                            }`}
                            style={{ 
                              backgroundColor: `${seg.color}15`, // 8% opacity
                              borderLeft: `2.5px solid ${seg.color}`,
                              paddingLeft: '6px'
                            }}
                            title={`${seg.type.toUpperCase()} | Emotion: ${seg.emotion}`}
                          >
                            {seg.text}{" "}
                          </span>
                        ))}
                      </div>

                      {/* Legend */}
                      <div className="flex flex-wrap gap-x-3 gap-y-1.5 text-[10px] text-zinc-500 pt-2 border-t border-[#1E1E2A]/50">
                        <span className="font-semibold uppercase tracking-wider text-zinc-600">Emotion Map:</span>
                        <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-[#F5C518]" /> <span>Happy</span></span>
                        <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-[#4A90D9]" /> <span>Sad</span></span>
                        <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-[#E84040]" /> <span>Angry</span></span>
                        <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-[#9B59B6]" /> <span>Suspenseful</span></span>
                        <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-[#A0A0A0]" /> <span>Neutral</span></span>
                      </div>
                    </div>
                  ) : (
                    <div className="flex-1 flex flex-col space-y-4">
                      <div className="flex-1 overflow-y-auto max-h-[300px] text-sm text-zinc-400 leading-relaxed bg-[#0B0B0F] p-4 rounded-xl border border-[#1E1E2A] custom-scrollbar whitespace-pre-wrap select-text">
                        {selectedStory.content}
                      </div>
                      
                      <div className="pt-2">
                        <button 
                          onClick={() => handleAnalyzeStory(selectedStory.id)}
                          disabled={isAnalyzing}
                          className="w-full bg-gradient-to-r from-[#7C5CFF] to-[#A78BFA] hover:from-[#6b4ae6] hover:to-[#9675e8] active:scale-[0.98] text-white font-semibold py-3 rounded-xl transition-all duration-200 shadow-lg shadow-[#7C5CFF]/20 flex items-center justify-center space-x-2 disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
                        >
                          {isAnalyzing ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" />
                              <span>Requesting analysis...</span>
                            </>
                          ) : (
                            <>
                              <Sparkles className="w-4 h-4" />
                              <span>Process NLP Pipeline (Phase 4)</span>
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-center text-zinc-500 py-16">
                  <FileText className="w-10 h-10 mb-2 text-zinc-600 opacity-60 animate-pulse" />
                  <p className="text-sm font-medium">Select a story to preview</p>
                </div>
              )}
            </div>
          </div>
        </section>

      </main>

      {/* Footer */}
      <footer className="border-t border-[#1E1E2A] py-6 px-6 bg-[#0B0B0F] mt-auto">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between text-xs text-zinc-600">
          <p>© {new Date().getFullYear()} StoryVoice AI. All rights reserved.</p>
          <div className="flex space-x-4 mt-2 sm:mt-0">
            <span>Powered by Next.js & FastAPI</span>
            <span>•</span>
            <span>Premium UI Design</span>
          </div>
        </div>
      </footer>

      {/* Styled custom scrollbar */}
      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 5px;
          height: 5px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: #0B0B0F;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #1E1E2A;
          border-radius: 99px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #7C5CFF/30;
        }
      `}</style>
    </div>
  );
}
