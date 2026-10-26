"use client";

import * as React from "react";
import {
  HelpCircle,
  Plus,
  Search,
  Filter,
  Bot,
  Trash2,
  Edit,
  FolderPlus,
  Sparkles,
  Layers,
  AlertTriangle,
  Clock,
  Car,
  ShieldAlert,
  Building,
  CreditCard,
  Pill,
  FileText,
  MapPin,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import {
  listHospitalInfo,
  updateHospitalInfo,
  deleteHospitalInfo,
  type HospitalInfoOut,
} from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { HospitalInfoDialog } from "@/components/hospital-info/HospitalInfoDialog";
import { toast } from "sonner";

// Helper icon picker based on category name
const getCategoryIcon = (category: string) => {
  const cat = category.toLowerCase();
  if (cat.includes("park")) return Car;
  if (cat.includes("emerg")) return ShieldAlert;
  if (cat.includes("timing") || cat.includes("hour")) return Clock;
  if (cat.includes("dept") || cat.includes("special")) return Building;
  if (cat.includes("insur") || cat.includes("bill") || cat.includes("pay")) return CreditCard;
  if (cat.includes("pharm") || cat.includes("med")) return Pill;
  if (cat.includes("report") || cat.includes("lab") || cat.includes("test")) return FileText;
  if (cat.includes("locat") || cat.includes("address") || cat.includes("where")) return MapPin;
  return HelpCircle;
};

export default function HospitalInfoPage() {
  const { hospitalId, hospital } = useHospital();

  const [entries, setEntries] = React.useState<HospitalInfoOut[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [selectedCategory, setSelectedCategory] = React.useState<string>("ALL");
  const [showInactive, setShowInactive] = React.useState(true);

  // Dialog state
  const [isDialogOpen, setIsDialogOpen] = React.useState(false);
  const [editingEntry, setEditingEntry] = React.useState<HospitalInfoOut | null>(null);
  const [defaultCategory, setDefaultCategory] = React.useState<string | undefined>(undefined);

  // Delete modal state
  const [deletingEntry, setDeletingEntry] = React.useState<HospitalInfoOut | null>(null);
  const [isDeleting, setIsDeleting] = React.useState(false);

  // Load entries from backend
  const loadEntries = React.useCallback(async () => {
    if (!hospitalId) return;
    setIsLoading(true);
    try {
      const page = await listHospitalInfo(hospitalId, {
        include_inactive: showInactive,
        limit: 100,
      });
      setEntries(page.items || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load hospital info";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, [hospitalId, showInactive]);

  React.useEffect(() => {
    loadEntries();
  }, [loadEntries]);

  // Handle active status toggle
  const handleToggleActive = async (entry: HospitalInfoOut) => {
    const newStatus = !entry.is_active;
    try {
      await updateHospitalInfo(entry.id, { is_active: newStatus });
      toast.success(
        `Entry marked ${newStatus ? "Active for AI" : "Inactive"}`
      );
      setEntries((prev) =>
        prev.map((e) => (e.id === entry.id ? { ...e, is_active: newStatus } : e))
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update entry";
      toast.error(msg);
    }
  };

  // Handle soft-delete
  const handleDeleteConfirm = async () => {
    if (!deletingEntry) return;
    setIsDeleting(true);
    try {
      await deleteHospitalInfo(deletingEntry.id);
      toast.success("FAQ entry deactivated and hidden from AI");
      setDeletingEntry(null);
      loadEntries();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete entry";
      toast.error(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  // Distinct category list
  const allCategories = React.useMemo(() => {
    const set = new Set<string>();
    entries.forEach((e) => e.category && set.add(e.category));
    return Array.from(set).sort();
  }, [entries]);

  // Filtered entries
  const filteredEntries = entries.filter((e) => {
    const matchesSearch =
      e.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.answer.toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.category.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesCategory =
      selectedCategory === "ALL" || e.category === selectedCategory;

    const matchesActive = showInactive || e.is_active;

    return matchesSearch && matchesCategory && matchesActive;
  });

  // Group filtered entries by category
  const groupedByCategory = React.useMemo(() => {
    const map = new Map<string, HospitalInfoOut[]>();
    filteredEntries.forEach((entry) => {
      const list = map.get(entry.category) || [];
      list.push(entry);
      map.set(entry.category, list);
    });
    return map;
  }, [filteredEntries]);

  const activeCount = entries.filter((e) => e.is_active).length;

  return (
    <div className="space-y-6">
      {/* Top Header & Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl">ℹ️</span>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Hospital Knowledge Base &amp; FAQ
            </h1>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            Verified answers injected into the AI receptionist&apos;s retrieval tools for bilingual caller queries.
          </p>
        </div>

        <Button
          onClick={() => {
            setEditingEntry(null);
            setDefaultCategory(undefined);
            setIsDialogOpen(true);
          }}
          className="gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Add FAQ Entry</span>
        </Button>
      </div>

      {/* Metrics Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 md:gap-4">
        <Card className="p-4 border-border bg-card shadow-xs">
          <span className="text-xs font-semibold text-muted-foreground uppercase">
            Total Entries
          </span>
          <div className="text-2xl font-extrabold text-foreground mt-1">
            {entries.length}
          </div>
        </Card>

        <Card className="p-4 border-border bg-card shadow-xs">
          <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase">
            Active for AI
          </span>
          <div className="text-2xl font-extrabold text-foreground mt-1">
            {activeCount}
          </div>
        </Card>

        <Card className="p-4 border-border bg-card shadow-xs">
          <span className="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase">
            Categories
          </span>
          <div className="text-2xl font-extrabold text-foreground mt-1">
            {allCategories.length}
          </div>
        </Card>

        <Card className="p-4 border-border bg-card shadow-xs">
          <span className="text-xs font-semibold text-purple-600 dark:text-purple-400 uppercase">
            AI Receptionist
          </span>
          <div className="text-sm font-bold text-foreground mt-2 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Retrieval Ready</span>
          </div>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-card p-3 rounded-xl border border-border">
        <div className="flex flex-1 flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
          {/* Search box */}
          <div className="relative flex-1 max-w-sm">
            <Search className="w-3.5 h-3.5 absolute left-3 top-3 text-muted-foreground" />
            <Input
              placeholder="Search question, answer, category..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-9 text-xs bg-background"
            />
          </div>

          {/* Category Dropdown Filter */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="h-9 px-3 text-xs bg-background border border-input rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
          >
            <option value="ALL">All Categories ({allCategories.length})</option>
            {allCategories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        {/* Include Inactive Toggle */}
        <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground cursor-pointer select-none self-end sm:self-center">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="rounded border-border text-blue-600 focus:ring-blue-500 cursor-pointer"
          />
          <span>Include inactive</span>
        </label>
      </div>

      {/* Grouped Knowledge Base Content */}
      {isLoading ? (
        <div className="p-16 text-center space-y-3">
          <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-muted-foreground">Loading hospital knowledge base...</p>
        </div>
      ) : groupedByCategory.size === 0 ? (
        /* Empty State */
        <Card className="p-12 text-center space-y-3 border-dashed border-2">
          <div className="w-12 h-12 rounded-2xl bg-muted text-muted-foreground flex items-center justify-center mx-auto">
            <HelpCircle className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-foreground">No knowledge entries found</h3>
          <p className="text-xs text-muted-foreground max-w-sm mx-auto">
            {searchQuery || selectedCategory !== "ALL"
              ? "No records matched your search query. Try clearing the filter."
              : "Add answers to frequent questions like parking, directions, or OPD timings."}
          </p>
          <Button
            size="sm"
            onClick={() => {
              setEditingEntry(null);
              setDefaultCategory(undefined);
              setIsDialogOpen(true);
            }}
            className="text-xs gap-1.5 bg-blue-600 text-white cursor-pointer mt-2"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create First Entry</span>
          </Button>
        </Card>
      ) : (
        /* Grouped Category Sections */
        <div className="space-y-8">
          {Array.from(groupedByCategory.entries()).map(([categoryName, categoryEntries]) => {
            const Icon = getCategoryIcon(categoryName);

            return (
              <section key={categoryName} className="space-y-3">
                {/* Category Header */}
                <div className="flex items-center justify-between pb-1.5 border-b border-border">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center">
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    <h2 className="text-base font-bold text-foreground">
                      {categoryName}
                    </h2>
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-muted font-semibold text-muted-foreground">
                      {categoryEntries.length}
                    </span>
                  </div>

                  {/* Inline Add to Category Button */}
                  <button
                    type="button"
                    onClick={() => {
                      setEditingEntry(null);
                      setDefaultCategory(categoryName);
                      setIsDialogOpen(true);
                    }}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
                  >
                    <Plus className="w-3 h-3" />
                    <span>Add to {categoryName}</span>
                  </button>
                </div>

                {/* Cards Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4">
                  {categoryEntries.map((item) => (
                    <Card
                      key={item.id}
                      className={`p-4 border-border bg-card shadow-xs flex flex-col justify-between transition-all hover:border-blue-500/40 ${
                        !item.is_active ? "opacity-60 bg-muted/20" : ""
                      }`}
                    >
                      <div className="space-y-2">
                        {/* Question Header */}
                        <div className="flex items-start justify-between gap-2">
                          <h3 className="text-sm font-bold text-foreground leading-snug">
                            {item.question}
                          </h3>
                        </div>

                        {/* Answer Text */}
                        <p className="text-xs text-muted-foreground leading-relaxed">
                          {item.answer}
                        </p>
                      </div>

                      {/* Card Footer: Status Toggle & Actions */}
                      <div className="pt-3 mt-3 border-t border-border flex items-center justify-between text-xs">
                        {/* Active toggle button */}
                        <button
                          type="button"
                          onClick={() => handleToggleActive(item)}
                          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold transition-all cursor-pointer border ${
                            item.is_active
                              ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/20"
                              : "bg-muted text-muted-foreground border-border hover:bg-muted/80"
                          }`}
                          title="Toggle whether AI answers this question"
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              item.is_active ? "bg-emerald-500" : "bg-muted-foreground"
                            }`}
                          />
                          <span>{item.is_active ? "AI Active" : "Disabled"}</span>
                        </button>

                        {/* Edit & Delete Actions */}
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => {
                              setEditingEntry(item);
                              setDefaultCategory(item.category);
                              setIsDialogOpen(true);
                            }}
                            className="p-1 rounded-md text-muted-foreground hover:text-blue-600 hover:bg-muted transition-colors cursor-pointer"
                            title="Edit entry"
                          >
                            <Edit className="w-3.5 h-3.5" />
                          </button>

                          <button
                            type="button"
                            onClick={() => setDeletingEntry(item)}
                            className="p-1 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors cursor-pointer"
                            title="Deactivate entry"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {/* Add / Edit FAQ Dialog */}
      <HospitalInfoDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        entry={editingEntry}
        defaultCategory={defaultCategory}
        existingCategories={allCategories}
        onSuccess={loadEntries}
      />

      {/* Delete / Deactivate Confirmation Dialog */}
      <Dialog
        open={!!deletingEntry}
        onOpenChange={(open) => !open && setDeletingEntry(null)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <div className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="w-5 h-5" />
              <DialogTitle className="text-base font-bold">
                Deactivate FAQ Entry?
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-muted-foreground pt-1">
              Soft-deleting &quot;{deletingEntry?.question}&quot; will hide it from the AI receptionist. Callers asking about this topic will be informed that hospital staff will assist them.
            </DialogDescription>
          </DialogHeader>

          <DialogFooter className="pt-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeletingEntry(null)}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={isDeleting}
              onClick={handleDeleteConfirm}
              className="text-xs gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>{isDeleting ? "Deactivating..." : "Confirm Deactivation"}</span>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
