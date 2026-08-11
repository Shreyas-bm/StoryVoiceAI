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
  AlertTriangle,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Download,
  RotateCcw,
  Headphones
} from "lucide-react";

// API Base URL - configure fallback to localhost
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Segment {
  type: "dialogue" | "narration";
  text: string;
  emotion: string;
  color: string;
  duration?: number;
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

  // Audio Generation States
  const [audioStatus, setAudioStatus] = useState<"none" | "pending" | "processing" | "completed" | "failed">("none");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioJobId, setAudioJobId] = useState<number | null>(null);
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false);
  const [narratorVoice, setNarratorVoice] = useState<"male" | "female">("male");
  
  // Custom Audio Player States
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const [dynamicStatusText, setDynamicStatusText] = useState("Initializing audio engine...");

  const fileInputRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioIntervalRef = useRef<any>(null);

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
        } else {
          // If status is 404 or any other error, stop polling
          clearInterval(interval);
          setIsAnalyzing(false);
          if (res.status === 404) {
            setErrorMessage("Story not found. The server may have restarted.");
          } else {
            setErrorMessage("Failed to fetch story analysis.");
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

  // Helper to format time MM:SS
  const formatTime = (timeInSeconds: number) => {
    if (isNaN(timeInSeconds)) return "00:00";
    const mins = Math.floor(timeInSeconds / 60);
    const secs = Math.floor(timeInSeconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  // Poll audio generation job status
  const pollAudioStatus = (storyId: number) => {
    if (audioIntervalRef.current) {
      clearInterval(audioIntervalRef.current);
    }
    
    let attempts = 0;
    const maxAttempts = 60; // 90 seconds (60 * 1.5s)
    
    audioIntervalRef.current = setInterval(async () => {
      attempts++;
      try {
        const res = await fetch(`${API_BASE_URL}/api/stories/${storyId}/audio-status`);
        if (res.ok) {
          const data = await res.json();
          setAudioStatus(data.status);
          setAudioUrl(data.audio_url);
          setAudioJobId(data.job_id);
          
          if (data.status === "completed" || data.status === "failed") {
            if (audioIntervalRef.current) {
              clearInterval(audioIntervalRef.current);
              audioIntervalRef.current = null;
            }
            if (data.status === "completed") {
              setSuccessMessage("Audiobook generated successfully!");
            } else {
              setErrorMessage("Audiobook generation failed.");
            }
          }
        } else {
          // If status is 404 or any other error, stop polling
          if (audioIntervalRef.current) {
            clearInterval(audioIntervalRef.current);
            audioIntervalRef.current = null;
          }
          setAudioStatus("failed");
          if (res.status === 404) {
            setErrorMessage("Story not found. The server may have restarted.");
          } else {
            setErrorMessage("Failed to fetch audio status.");
          }
        }
      } catch (err) {
        console.error("Error polling audio status:", err);
      }
      
      if (attempts >= maxAttempts) {
        if (audioIntervalRef.current) {
          clearInterval(audioIntervalRef.current);
          audioIntervalRef.current = null;
        }
        setAudioStatus("failed");
        setErrorMessage("Audio generation timed out. Please try again.");
      }
    }, 1500);
  };

  // Fetch audio status for a story
  const fetchAudioStatus = async (storyId: number) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/stories/${storyId}/audio-status`);
      if (res.ok) {
        const data = await res.json();
        setAudioStatus(data.status);
        setAudioUrl(data.audio_url);
        setAudioJobId(data.job_id);
        
        if (data.status === "pending" || data.status === "processing") {
          pollAudioStatus(storyId);
        }
      } else {
        setAudioStatus("none");
        setAudioUrl(null);
        setAudioJobId(null);
      }
    } catch (err) {
      console.error("Failed to fetch audio status:", err);
    }
  };

  // Trigger audio generation
  const handleGenerateAudio = async (storyId: number) => {
    // Stop any active audio playback
    if (audioRef.current) {
      try {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      } catch (err) {
        console.error("Failed to stop playback during regeneration:", err);
      }
    }
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
    
    setIsGeneratingAudio(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setAudioStatus("pending");
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/stories/${storyId}/generate-audio?narrator_voice=${narratorVoice}`, {
        method: "POST",
      });
      
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to trigger audio generation");
      }
      
      const data = await res.json();
      setAudioStatus(data.status);
      setAudioJobId(data.job_id);
      
      pollAudioStatus(storyId);
    } catch (err: any) {
      setErrorMessage(err.message || "An error occurred while generating audio.");
      setAudioStatus("failed");
    } finally {
      setIsGeneratingAudio(false);
    }
  };

  // Audio Player Event Handlers
  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleDurationChange = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleAudioEnded = () => {
    setIsPlaying(false);
    setCurrentTime(0);
  };

  const togglePlayPause = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().catch(err => {
        console.error("Audio playback failed:", err);
      });
      setIsPlaying(true);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!audioRef.current) return;
    const newTime = parseFloat(e.target.value);
    audioRef.current.currentTime = newTime;
    setCurrentTime(newTime);
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setVolume(val);
    setIsMuted(val === 0);
    if (audioRef.current) {
      audioRef.current.volume = val;
      audioRef.current.muted = val === 0;
    }
  };

  const toggleMute = () => {
    if (!audioRef.current) return;
    const nextMute = !isMuted;
    setIsMuted(nextMute);
    audioRef.current.muted = nextMute;
  };

  const cyclePlaybackRate = () => {
    if (!audioRef.current) return;
    let nextRate = 1.0;
    if (playbackRate === 1.0) nextRate = 1.25;
    else if (playbackRate === 1.25) nextRate = 1.5;
    else if (playbackRate === 1.5) nextRate = 2.0;
    else nextRate = 1.0;
    
    setPlaybackRate(nextRate);
    audioRef.current.playbackRate = nextRate;
  };

  // Find active segment based on current audio playback time
  const getActiveSegmentIndex = () => {
    if (!selectedStory || !selectedStory.annotated_content || audioStatus !== "completed") return -1;
    const segments = selectedStory.annotated_content.segments;
    let accumulatedTime = 0;
    for (let i = 0; i < segments.length; i++) {
      const segDuration = segments[i].duration || 0;
      if (currentTime >= accumulatedTime && currentTime < accumulatedTime + segDuration) {
        return i;
      }
      accumulatedTime += segDuration;
    }
    // Fallback: if currentTime is at/near the very end
    if (currentTime >= accumulatedTime && segments.length > 0 && accumulatedTime > 0) {
      return segments.length - 1;
    }
    return -1;
  };
  
  const activeSegmentIndex = getActiveSegmentIndex();

  // Handle clicking a segment to seek to its start time
  const handleSegmentClick = (idx: number) => {
    if (!selectedStory || !selectedStory.annotated_content || !audioRef.current || audioStatus !== "completed") return;
    const segments = selectedStory.annotated_content.segments;
    let targetTime = 0;
    for (let i = 0; i < idx; i++) {
      targetTime += segments[i].duration || 0;
    }
    audioRef.current.currentTime = targetTime;
    setCurrentTime(targetTime);
    if (!isPlaying) {
      audioRef.current.play().catch(err => {
        console.error("Playback failed after seeking segment:", err);
      });
      setIsPlaying(true);
    }
  };

  // Auto-scroll active segment into view
  useEffect(() => {
    if (activeSegmentIndex !== -1) {
      const activeEl = document.getElementById(`segment-${activeSegmentIndex}`);
      if (activeEl) {
        activeEl.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        });
      }
    }
  }, [activeSegmentIndex]);

  // Reset audio states and poll when story changes
  useEffect(() => {
    if (selectedStory) {
      setIsPlaying(false);
      setCurrentTime(0);
      setDuration(0);
      
      if (audioIntervalRef.current) {
        clearInterval(audioIntervalRef.current);
        audioIntervalRef.current = null;
      }
      
      setAudioStatus("none");
      setAudioUrl(null);
      setAudioJobId(null);
      
      fetchAudioStatus(selectedStory.id);
      
      // Auto-poll NLP analysis if currently pending or processing
      if (selectedStory.nlp_status === "processing" || selectedStory.nlp_status === "pending") {
        setIsAnalyzing(true);
        pollAnalysis(selectedStory.id);
      }
    }
  }, [selectedStory?.id]);

  // Cycle status texts during audio generation
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (audioStatus === "pending" || audioStatus === "processing") {
      const statuses = [
        "Initializing audio generation task...",
        "Reading character voice configurations...",
        "Synthesizing narration sections (warm narrator)...",
        "Synthesizing dialogue sections...",
        "Applying emotion profiles (happy, sad, suspenseful)...",
        "Mixing audio files and adjusting pitch...",
        "Merging audio segments into final audiobook...",
        "Uploading audio to storage...",
        "Finishing up..."
      ];
      let idx = 0;
      setDynamicStatusText(statuses[0]);
      interval = setInterval(() => {
        idx = (idx + 1) % statuses.length;
        setDynamicStatusText(statuses[idx]);
      }, 2500);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [audioStatus]);

  // Clean up interval on unmount
  useEffect(() => {
    return () => {
      if (audioIntervalRef.current) {
        clearInterval(audioIntervalRef.current);
      }
    };
  }, []);

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
    <div className="min-h-screen bg-[#0A0E17] text-zinc-100 flex flex-col font-sans selection:bg-[#8B5CF6]/30 selection:text-white relative overflow-hidden">
      {/* Soft background glow effects */}
      <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-[#8B5CF6]/5 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute -bottom-40 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-[#00D4FF]/3 rounded-full blur-[120px] pointer-events-none" />

      {/* Top Header */}
      <header className="border-b border-white/5 bg-[#0A0E17]/60 backdrop-blur-md sticky top-0 z-50 px-4 sm:px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3 group cursor-pointer" onClick={() => setSelectedStory(null)}>
            <div className="p-2 bg-[#8B5CF6]/10 border border-[#8B5CF6]/20 rounded-xl transition-all duration-300">
              <Headphones className="w-5 h-5 text-[#A78BFA]" />
            </div>
            <div>
              <h1 className="font-bold text-lg tracking-tight text-white">
                StoryVoice <span className="text-[#8B5CF6]">AI</span>
              </h1>
              <p className="text-[9px] text-zinc-500 font-semibold uppercase tracking-wider">Minimal Podcast Editor</p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-[11px] bg-[#111827]/80 border border-white/5 px-3 py-1.5 rounded-full text-zinc-400 flex items-center space-x-1.5 shadow-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-medium">Active</span>
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-2xl w-full mx-auto p-4 sm:p-6 md:py-12 z-10 flex flex-col justify-center space-y-8">
        
        {/* Story Selector / Library Panel */}
        <div className="flex flex-col sm:flex-row justify-between sm:items-center bg-[#111827]/40 border border-white/5 rounded-2xl p-4 backdrop-blur-md gap-3 shadow-lg shadow-black/10">
          <div>
            <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">Selected Story</span>
            <span className="text-[10px] text-zinc-500">Pick an existing story or write a new one</span>
          </div>
          <div className="flex items-center space-x-2">
            <select
              value={selectedStory?.id || ""}
              onChange={(e) => {
                if (e.target.value === "") {
                  setSelectedStory(null);
                } else {
                  const story = stories.find(s => s.id === Number(e.target.value));
                  if (story) setSelectedStory(story);
                }
              }}
              className="bg-[#111827] border border-white/10 text-zinc-200 text-xs font-semibold rounded-xl px-4 py-2.5 focus:outline-none focus:border-[#8B5CF6] cursor-pointer max-w-[220px] transition-colors"
            >
              <option value="">+ Write New Story</option>
              {stories.map(s => (
                <option key={s.id} value={s.id}>{s.title}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Dynamic Card Display */}
        {!selectedStory ? (
          /* STORY CREATION CARD (Centered Input Area) */
          <div className="bg-[#111827]/60 border border-white/5 rounded-3xl p-6 sm:p-8 shadow-2xl relative backdrop-blur-md flex flex-col space-y-6">
            <div className="flex justify-between items-center border-b border-white/5 pb-4">
              <div className="flex bg-[#0A0E17] p-1 rounded-xl border border-white/5">
                <button
                  type="button"
                  onClick={() => { setActiveTab("write"); setErrorMessage(null); }}
                  className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    activeTab === "write" ? "bg-[#8B5CF6] text-white shadow-sm" : "text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  Write Content
                </button>
                <button
                  type="button"
                  onClick={() => { setActiveTab("upload"); setErrorMessage(null); }}
                  className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    activeTab === "upload" ? "bg-[#8B5CF6] text-white shadow-sm" : "text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  Upload File
                </button>
              </div>
              <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold">New Audiobook</span>
            </div>

            {errorMessage && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded-xl flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}
            {successMessage && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs rounded-xl flex items-center space-x-2">
                <Check className="w-4 h-4 shrink-0" />
                <span>{successMessage}</span>
              </div>
            )}

            {activeTab === "write" ? (
              <form onSubmit={handleSubmitStory} className="space-y-6">
                <div className="space-y-2">
                  <label htmlFor="write-title" className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Story Title</label>
                  <input
                    id="write-title"
                    type="text"
                    placeholder="E.g., The Midnight Whispers"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    disabled={isSubmitting}
                    className="w-full bg-[#0A0E17] border border-white/5 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#8B5CF6] focus:ring-1 focus:ring-[#8B5CF6] text-zinc-100 placeholder-zinc-600 transition-all duration-200"
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="write-content" className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Story Content</label>
                  <textarea
                    id="write-content"
                    placeholder="Write or paste your paragraphs here. Dialogues with quotes are automatically detected."
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    disabled={isSubmitting}
                    rows={8}
                    className="w-full bg-[#0A0E17] border border-white/5 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#8B5CF6] focus:ring-1 focus:ring-[#8B5CF6] text-zinc-100 placeholder-zinc-600 transition-all duration-200 resize-none min-h-[180px] leading-relaxed"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full bg-[#8B5CF6] hover:bg-[#7c4dff] active:scale-[0.98] text-white font-semibold py-3.5 rounded-xl transition-all duration-200 shadow-lg shadow-[#8B5CF6]/10 flex items-center justify-center space-x-2 disabled:opacity-50 disabled:pointer-events-none cursor-pointer text-sm"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Extracting Content...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      <span>Load and Parse Story</span>
                    </>
                  )}
                </button>
              </form>
            ) : (
              <form onSubmit={handleUploadStory} className="space-y-6">
                <div className="space-y-2">
                  <label htmlFor="upload-title" className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Story Title (Optional)</label>
                  <input
                    id="upload-title"
                    type="text"
                    placeholder="Determined from filename if left blank..."
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    disabled={isSubmitting}
                    className="w-full bg-[#0A0E17] border border-white/5 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#8B5CF6] focus:ring-1 focus:ring-[#8B5CF6] text-zinc-100 placeholder-zinc-600 transition-all duration-200"
                  />
                </div>
                
                <div className="space-y-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Upload Document</span>
                  <div
                    onClick={() => !isSubmitting && fileInputRef.current?.click()}
                    className={`w-full border border-dashed rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all duration-200 ${
                      selectedFile 
                        ? "border-[#8B5CF6]/70 bg-[#8B5CF6]/5" 
                        : "border-white/5 bg-[#0A0E17] hover:border-[#8B5CF6]/40"
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
                        <div className="mx-auto w-10 h-10 rounded-full bg-[#8B5CF6]/15 flex items-center justify-center text-[#8B5CF6]">
                          <FileUp className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="text-xs font-semibold text-zinc-200 truncate max-w-[260px]">
                            {selectedFile.name}
                          </p>
                          <p className="text-[10px] text-zinc-500">
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
                          className="text-[10px] text-red-400 hover:text-red-300 font-semibold underline inline-flex items-center space-x-1"
                        >
                          <Trash2 className="w-3 h-3" />
                          <span>Remove</span>
                        </button>
                      </div>
                    ) : (
                      <div className="text-center space-y-3">
                        <div className="mx-auto w-10 h-10 rounded-full bg-white/5 flex items-center justify-center text-zinc-400">
                          <UploadCloud className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="text-xs font-medium text-zinc-300">
                            Drag & drop or <span className="text-[#8B5CF6] underline">browse</span>
                          </p>
                          <p className="text-[10px] text-zinc-500 mt-1">
                            Supports PDF, DOCX, TXT
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting || !selectedFile}
                  className="w-full bg-[#8B5CF6] hover:bg-[#7c4dff] active:scale-[0.98] text-white font-semibold py-3.5 rounded-xl transition-all duration-200 shadow-lg shadow-[#8B5CF6]/10 flex items-center justify-center space-x-2 disabled:opacity-50 disabled:pointer-events-none cursor-pointer text-sm"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Parsing Document...</span>
                    </>
                  ) : (
                    <>
                      <FileText className="w-4 h-4" />
                      <span>Load and Parse Story</span>
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        ) : (
          /* STORY PREVIEW & AUDIO PLAYER CARD (Premium layout, waveforms, play buttons) */
          <div className="bg-[#111827]/60 border border-white/5 rounded-3xl p-6 sm:p-8 shadow-2xl relative backdrop-blur-md flex flex-col space-y-6">
            
            {/* Header info */}
            <div className="flex justify-between items-start border-b border-white/5 pb-4">
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">{selectedStory.title}</h2>
                <p className="text-[10px] text-zinc-500 mt-1 uppercase tracking-wider font-semibold">
                  {selectedStory.nlp_status === "completed" 
                    ? `Narrative Analyzed (${selectedStory.content.length} chars)` 
                    : `Text Loaded (${selectedStory.content.length} chars)`}
                </p>
              </div>
              {selectedStory.nlp_status && (
                <span className={`text-[9px] font-bold uppercase px-2.5 py-1 rounded-full border tracking-wider ${
                  selectedStory.nlp_status === "completed"
                    ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                    : selectedStory.nlp_status === "processing"
                    ? "bg-amber-500/10 border-amber-500/20 text-amber-400 animate-pulse"
                    : selectedStory.nlp_status === "failed"
                    ? "bg-red-500/10 border-red-500/20 text-red-400"
                    : "bg-zinc-500/10 border-zinc-500/20 text-zinc-400"
                }`}>
                  {selectedStory.nlp_status}
                </span>
              )}
            </div>

            {errorMessage && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded-xl flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}
            {successMessage && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs rounded-xl flex items-center space-x-2">
                <Check className="w-4 h-4 shrink-0" />
                <span>{successMessage}</span>
              </div>
            )}

            {/* Story Text Box / Reader */}
            {selectedStory.nlp_status === "processing" ? (
              <div className="flex flex-col items-center justify-center py-12 space-y-4">
                <Loader2 className="w-8 h-8 animate-spin text-[#8B5CF6]" />
                <div className="space-y-1 text-center">
                  <p className="text-sm font-semibold text-zinc-200">Analyzing story narrative</p>
                  <p className="text-xs text-zinc-500 max-w-[280px]">
                    Splitting paragraphs, mapping emotional tones, and identifying characters...
                  </p>
                </div>
              </div>
            ) : selectedStory.nlp_status === "completed" && selectedStory.annotated_content ? (
              <div className="space-y-4">
                {/* Options panel: Voice selector & toggle highlights */}
                <div className="space-y-3">
                  {/* Voice Selector */}
                  <div className="flex items-center justify-between bg-[#0A0E17]/60 border border-white/5 p-3 rounded-2xl">
                    <div>
                      <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider block">Narrator Voice</span>
                      <span className="text-[9px] text-zinc-500">Pick narrator gender profile</span>
                    </div>
                    <div className="flex bg-[#111827] p-0.5 rounded-lg border border-white/10 shrink-0">
                      <button
                        type="button"
                        onClick={() => setNarratorVoice("male")}
                        className={`px-3 py-1.5 text-[11px] font-bold rounded-md transition-all cursor-pointer ${
                          narratorVoice === "male" ? "bg-[#8B5CF6] text-white shadow-sm" : "text-zinc-500 hover:text-zinc-300"
                        }`}
                      >
                        Male
                      </button>
                      <button
                        type="button"
                        onClick={() => setNarratorVoice("female")}
                        className={`px-3 py-1.5 text-[11px] font-bold rounded-md transition-all cursor-pointer ${
                          narratorVoice === "female" ? "bg-[#8B5CF6] text-white shadow-sm" : "text-zinc-500 hover:text-zinc-300"
                        }`}
                      >
                        Female
                      </button>
                    </div>
                  </div>

                </div>

                {/* Narrative Viewer (Clean typography, generous padding) */}
                <div className="bg-[#0A0E17] border border-white/5 rounded-2xl p-6 text-sm text-zinc-300 leading-relaxed max-h-[220px] overflow-y-auto custom-scrollbar select-text space-y-1">
                  {selectedStory.annotated_content.segments.map((seg, idx) => {
                    const isActive = idx === activeSegmentIndex;
                    return (
                      <span 
                        key={idx} 
                        id={`segment-${idx}`}
                        onClick={() => handleSegmentClick(idx)}
                        className={`inline transition-all duration-200 ${
                          isActive 
                            ? "text-[#8B5CF6] font-medium" 
                            : "opacity-85 hover:opacity-100"
                        } ${
                          seg.type === "dialogue" ? "font-semibold" : ""
                        } ${
                          audioStatus === "completed" ? "cursor-pointer" : "cursor-help"
                        }`}
                        title={
                          audioStatus === "completed" 
                            ? `Click to seek here | ${seg.type} | ${seg.emotion}`
                            : `${seg.type} | ${seg.emotion}`
                        }
                      >
                        {seg.text}{" "}
                      </span>
                    );
                  })}
                </div>

                {/* AUDIO CONTROLLER CONTAINER */}
                <div className="border-t border-white/5 pt-6 space-y-4">
                  
                  {/* Action states for Audio */}
                  {audioStatus === "none" && (
                    <button
                      onClick={() => handleGenerateAudio(selectedStory.id)}
                      disabled={isGeneratingAudio}
                      className="w-full bg-[#8B5CF6] hover:bg-[#7c4dff] active:scale-[0.99] text-white font-semibold py-3 px-6 rounded-2xl transition-all duration-200 shadow-lg shadow-[#8B5CF6]/15 flex items-center justify-center space-x-2 cursor-pointer disabled:opacity-50 text-sm"
                    >
                      {isGeneratingAudio ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Generating Audio track...</span>
                        </>
                      ) : (
                        <>
                          <Music className="w-4 h-4" />
                          <span>Generate Audiobook Audio</span>
                        </>
                      )}
                    </button>
                  )}

                  {(audioStatus === "pending" || audioStatus === "processing") && (
                    <div className="bg-[#0A0E17]/40 border border-white/5 rounded-2xl p-5 flex flex-col space-y-3 relative overflow-hidden">
                      <div className="absolute top-0 left-0 right-0 h-[2px] bg-[#8B5CF6] animate-pulse" />
                      
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <Loader2 className="w-4 h-4 animate-spin text-[#8B5CF6]" />
                          <span className="text-xs font-semibold text-zinc-300">
                            {audioStatus === "pending" ? "Queueing audio pipeline..." : "Synthesizing dialogue voices..."}
                          </span>
                        </div>
                        <span className="text-[9px] text-zinc-500 font-mono uppercase tracking-wider">Loading</span>
                      </div>

                      <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden relative">
                        <div className="absolute top-0 bottom-0 left-0 w-1/3 bg-[#8B5CF6] rounded-full animate-shimmer-progress" />
                      </div>

                      <p className="text-[10px] text-zinc-400 italic text-center">
                        {dynamicStatusText}
                      </p>
                    </div>
                  )}

                  {audioStatus === "failed" && (
                    <div className="bg-red-500/5 border border-red-500/10 rounded-2xl p-5 flex flex-col space-y-3">
                      <div className="flex items-center space-x-2 text-red-400">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span className="text-xs font-semibold">Audio generation failed</span>
                      </div>
                      <p className="text-[11px] text-zinc-500">
                        An error occurred while synthesizing the dialogue voices. Please verify text formatting and retry.
                      </p>
                      <button
                        onClick={() => handleGenerateAudio(selectedStory.id)}
                        className="w-full bg-[#111827] border border-white/5 hover:border-red-500/30 text-zinc-300 font-semibold py-2.5 rounded-xl text-xs transition-colors flex items-center justify-center space-x-2 cursor-pointer"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>Retry Generation</span>
                      </button>
                    </div>
                  )}

                  {/* PREMIUM PODCAST AUDIO PLAYER */}
                  {audioStatus === "completed" && audioUrl && (
                    <div className="bg-[#0A0E17]/60 border border-white/5 rounded-2xl p-6 flex flex-col items-center space-y-6 shadow-inner">
                      
                      {/* Hidden HTML5 Audio Element */}
                      <audio
                        ref={audioRef}
                        src={audioUrl.startsWith("http") ? audioUrl : `${API_BASE_URL}${audioUrl}`}
                        onTimeUpdate={handleTimeUpdate}
                        onDurationChange={handleDurationChange}
                        onEnded={handleAudioEnded}
                      />
                      
                      {/* Simple Dynamic Waveform Visualizer */}
                      <div className="flex items-end justify-center space-x-1 h-12 w-full max-w-xs px-2">
                        {Array.from({ length: 32 }).map((_, i) => {
                          const mid = 16;
                          const dist = Math.abs(i - mid);
                          const baseHeight = Math.max(10, 85 - dist * 4.5);
                          return (
                            <div
                              key={i}
                              className={`w-[2.5px] bg-[#8B5CF6] rounded-full transition-all duration-300`}
                              style={{
                                height: isPlaying ? '100%' : `${baseHeight}%`,
                                maxHeight: `${baseHeight}%`,
                                opacity: isPlaying ? 0.95 : 0.25,
                                animationName: isPlaying ? 'wave-bounce' : 'none',
                                animationDuration: '1.1s',
                                animationTimingFunction: 'ease-in-out',
                                animationIterationCount: 'infinite',
                                animationDelay: `${(i % 8) * 0.12}s`,
                                transformOrigin: 'bottom'
                              }}
                            />
                          );
                        })}
                      </div>

                      {/* Scrubber / Progress timeline */}
                      <div className="w-full flex items-center space-x-3">
                        <span className="text-[10px] text-zinc-500 font-mono w-10 text-right">
                          {formatTime(currentTime)}
                        </span>
                        <input
                          type="range"
                          min={0}
                          max={duration || 100}
                          value={currentTime}
                          onChange={handleSeek}
                          className="flex-1 h-1 bg-white/5 rounded-lg appearance-none cursor-pointer accent-[#8B5CF6] hover:accent-[#a78bfa] focus:outline-none"
                        />
                        <span className="text-[10px] text-zinc-500 font-mono w-10">
                          {formatTime(duration)}
                        </span>
                      </div>

                      {/* Controls Row */}
                      <div className="w-full flex items-center justify-between">
                        
                        {/* Speed controller */}
                        <button
                          onClick={cyclePlaybackRate}
                          className="text-[10px] font-bold font-mono text-zinc-400 bg-[#111827] border border-white/5 px-2.5 py-1.5 rounded-lg hover:text-white transition-colors cursor-pointer"
                        >
                          {playbackRate}x
                        </button>

                        {/* Large pulsing Play / Pause button */}
                        <div className="relative">
                          <button
                            onClick={togglePlayPause}
                            className={`w-14 h-14 rounded-full bg-[#8B5CF6] text-white flex items-center justify-center shadow-lg transition-all duration-300 cursor-pointer hover:scale-105 active:scale-95 ${
                              isPlaying ? 'animate-custom-pulse shadow-[#8B5CF6]/30' : ''
                            }`}
                          >
                            {isPlaying ? (
                              <Pause className="w-5 h-5 fill-white" />
                            ) : (
                              <Play className="w-5 h-5 fill-white translate-x-[1.5px]" />
                            )}
                          </button>
                        </div>

                        {/* Mute and volume */}
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={toggleMute}
                            className="text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer"
                          >
                            {isMuted || volume === 0 ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                          </button>
                          <input
                            type="range"
                            min={0}
                            max={1}
                            step={0.05}
                            value={isMuted ? 0 : volume}
                            onChange={handleVolumeChange}
                            className="w-12 h-1 bg-white/5 rounded-lg appearance-none cursor-pointer accent-[#8B5CF6]"
                          />
                        </div>

                      </div>

                      {/* Download and regenerate actions */}
                      <div className="w-full border-t border-white/5 pt-4 flex justify-end items-center space-x-2">
                        <button
                          onClick={() => handleGenerateAudio(selectedStory.id)}
                          className="px-3 py-1.5 bg-[#111827] hover:bg-[#111827]/80 border border-white/5 hover:border-[#8B5CF6]/20 rounded-xl text-[10px] font-bold text-zinc-400 hover:text-zinc-200 transition-all cursor-pointer flex items-center space-x-1.5"
                          title="Regenerate audiobook track"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>Regenerate</span>
                        </button>
                        <a
                          href={audioUrl.startsWith("http") ? audioUrl : `${API_BASE_URL}${audioUrl}`}
                          download={`storyvoice_${selectedStory.id}.wav`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-3 py-1.5 bg-[#8B5CF6]/10 hover:bg-[#8B5CF6]/20 border border-[#8B5CF6]/25 rounded-xl text-[10px] font-bold text-[#A78BFA] hover:text-[#C084FC] transition-all cursor-pointer flex items-center space-x-1.5"
                          title="Download final audio file"
                        >
                          <Download className="w-3 h-3" />
                          <span>Download WAV</span>
                        </a>
                      </div>

                    </div>
                  )}

                </div>
              </div>
            ) : (
              /* If story created but NLP not run yet */
              <div className="space-y-4">
                <div className="bg-[#0A0E17] border border-white/5 rounded-2xl p-6 text-sm text-zinc-400 leading-relaxed max-h-[220px] overflow-y-auto custom-scrollbar select-text whitespace-pre-wrap">
                  {selectedStory.content}
                </div>
                
                <button 
                  onClick={() => handleAnalyzeStory(selectedStory.id)}
                  disabled={isAnalyzing}
                  className="w-full bg-[#8B5CF6] hover:bg-[#7c4dff] active:scale-[0.98] text-white font-semibold py-3.5 rounded-xl transition-all duration-200 shadow-lg shadow-[#8B5CF6]/15 flex items-center justify-center space-x-2 disabled:opacity-50 disabled:pointer-events-none cursor-pointer text-sm"
                >
                  {isAnalyzing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Running NLP Engine...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      <span>Process Narrative Pipeline</span>
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8 px-4 sm:px-6 bg-[#0A0E17]/60 mt-auto z-10">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between text-[11px] text-zinc-600 gap-2">
          <p>© {new Date().getFullYear()} StoryVoice AI. Zero data persisted locally.</p>
          <div className="flex space-x-4">
            <span>Powered by Next.js & FastAPI</span>
            <span>•</span>
            <span>Premium Calm UI</span>
          </div>
        </div>
      </footer>

      {/* Styled custom scrollbar & animations */}
      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
          height: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.08);
          border-radius: 99px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(139, 92, 246, 0.25);
        }
        @keyframes shimmer-progress {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(200%); }
        }
        .animate-shimmer-progress {
          animation: shimmer-progress 2s infinite linear;
        }
      `}</style>
    </div>
  );
}
