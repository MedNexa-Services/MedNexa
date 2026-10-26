"use client";

import * as React from "react";
import Link from "next/link";
import {
  Stethoscope,
  Plus,
  Search,
  Filter,
  Calendar,
  Clock,
  Trash2,
  Edit,
  ExternalLink,
  CheckCircle2,
  XCircle,
  MoreVertical,
  AlertTriangle,
} from "lucide-react";
import { listDoctors, updateDoctor, deleteDoctor, type DoctorOut } from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DoctorFormDialog } from "@/components/doctors/DoctorFormDialog";
import { toast } from "sonner";

const DAY_LABELS: Record<number, string> = {
  1: "Mon",
  2: "Tue",
  3: "Wed",
  4: "Thu",
  5: "Fri",
  6: "Sat",
  7: "Sun",
};

export default function DoctorsPage() {
  const { hospitalId } = useHospital();

  const [doctors, setDoctors] = React.useState<DoctorOut[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [selectedDept, setSelectedDept] = React.useState<string>("ALL");
  const [showInactive, setShowInactive] = React.useState(true);

  // Dialog state
  const [isAddModalOpen, setIsAddModalOpen] = React.useState(false);
  const [editingDoctor, setEditingDoctor] = React.useState<DoctorOut | null>(null);

  // Delete confirmation modal state
  const [deletingDoctor, setDeletingDoctor] = React.useState<DoctorOut | null>(null);
  const [isDeleting, setIsDeleting] = React.useState(false);

  // Fetch doctors from backend
  const fetchDoctors = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const page = await listDoctors({
        hospital_id: hospitalId,
        include_inactive: showInactive,
        limit: 100,
      });
      setDoctors(page.items || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load doctors";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, [hospitalId, showInactive]);

  React.useEffect(() => {
    fetchDoctors();
  }, [fetchDoctors]);

  // Handle active/inactive status toggle
  const handleToggleStatus = async (doc: DoctorOut, e: React.MouseEvent) => {
    e.stopPropagation();
    const newStatus = !doc.is_active;

    try {
      await updateDoctor(doc.id, { is_active: newStatus });
      toast.success(
        `${doc.name} is now ${newStatus ? "Active" : "Inactive"}`
      );
      // Optimistic update
      setDoctors((prev) =>
        prev.map((d) => (d.id === doc.id ? { ...d, is_active: newStatus } : d))
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update doctor status";
      toast.error(msg);
    }
  };

  // Handle soft-delete
  const handleDeleteConfirm = async () => {
    if (!deletingDoctor) return;
    setIsDeleting(true);

    try {
      await deleteDoctor(deletingDoctor.id);
      toast.success(`Deactivated ${deletingDoctor.name}`);
      setDeletingDoctor(null);
      fetchDoctors();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to remove doctor";
      toast.error(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  // Unique departments for filter dropdown
  const departments = React.useMemo(() => {
    const set = new Set<string>();
    doctors.forEach((d) => d.department && set.add(d.department));
    return Array.from(set).sort();
  }, [doctors]);

  // Filtered list
  const filteredDoctors = doctors.filter((doc) => {
    const matchesSearch =
      doc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.speciality.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.department.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesDept = selectedDept === "ALL" || doc.department === selectedDept;
    const matchesActive = showInactive || doc.is_active;

    return matchesSearch && matchesDept && matchesActive;
  });

  const formatTime = (timeStr: string) => {
    if (!timeStr) return "";
    const [h, m] = timeStr.split(":");
    const hour = parseInt(h, 10);
    const ampm = hour >= 12 ? "PM" : "AM";
    const formattedHour = hour % 12 || 12;
    return `${formattedHour}:${m} ${ampm}`;
  };

  // Initials for avatar
  const getInitials = (name: string) => {
    const parts = name.replace(/^Dr\.\s*/i, "").split(" ");
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return parts[0]?.substring(0, 2).toUpperCase() || "DR";
  };

  const activeCount = doctors.filter((d) => d.is_active).length;
  const totalSlotsDaily = doctors
    .filter((d) => d.is_active)
    .reduce((sum, d) => sum + (d.max_daily_appointments || 0), 0);

  return (
    <div className="space-y-6">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl">👨‍⚕️</span>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Doctors &amp; Medical Staff
            </h1>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage hospital practitioners, daily appointment caps, and weekly shift availability.
          </p>
        </div>

        <Button
          onClick={() => {
            setEditingDoctor(null);
            setIsAddModalOpen(true);
          }}
          className="gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Add New Doctor</span>
        </Button>
      </div>

      {/* Metrics Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 md:gap-4">
        <Card className="p-4 border-border bg-card shadow-xs">
          <span className="text-xs font-semibold text-muted-foreground uppercase">
            Total Staff
          </span>
          <div className="text-2xl font-extrabold text-foreground mt-1">
            {doctors.length}
          </div>
        </Card>

        <Card className="p-4 border-border bg-card shadow-xs">
          <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase">
            Active Doctors
          </span>
          <div className="text-2xl font-extrabold text-foreground mt-1">
            {activeCount}
          </div>
        </Card>

        <Card className="p-4 border-border bg-card shadow-xs">
          <span className="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase">
            Departments
          </span>
          <div className="text-2xl font-extrabold text-foreground mt-1">
            {departments.length}
          </div>
        </Card>

        <Card className="p-4 border-border bg-card shadow-xs">
          <span className="text-xs font-semibold text-purple-600 dark:text-purple-400 uppercase">
            Daily Capacity
          </span>
          <div className="text-2xl font-extrabold text-foreground mt-1">
            {totalSlotsDaily} <span className="text-xs font-normal text-muted-foreground">slots</span>
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
              placeholder="Search by name, speciality, department..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-9 text-xs bg-background"
            />
          </div>

          {/* Department Filter */}
          <select
            value={selectedDept}
            onChange={(e) => setSelectedDept(e.target.value)}
            className="h-9 px-3 text-xs bg-background border border-input rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
          >
            <option value="ALL">All Departments ({departments.length})</option>
            {departments.map((dept) => (
              <option key={dept} value={dept}>
                {dept}
              </option>
            ))}
          </select>
        </div>

        {/* Show Inactive Toggle */}
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

      {/* Doctors Table */}
      <Card className="border-border bg-card overflow-hidden shadow-xs">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex items-center justify-between gap-4 py-2 border-b border-border/50">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-muted animate-pulse" />
                  <div className="space-y-1.5">
                    <div className="w-32 h-3.5 bg-muted animate-pulse rounded" />
                    <div className="w-20 h-2.5 bg-muted/60 animate-pulse rounded" />
                  </div>
                </div>
                <div className="hidden sm:block space-y-1.5">
                  <div className="w-24 h-3 bg-muted animate-pulse rounded" />
                  <div className="w-16 h-2 bg-muted/60 animate-pulse rounded" />
                </div>
                <div className="hidden md:flex gap-1">
                  {[1, 2, 3, 4].map((d) => (
                    <div key={d} className="w-6 h-5 rounded bg-muted animate-pulse" />
                  ))}
                </div>
                <div className="w-16 h-6 rounded-full bg-muted animate-pulse" />
                <div className="w-20 h-7 rounded bg-muted animate-pulse" />
              </div>
            ))}
          </div>
        ) : filteredDoctors.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-muted text-muted-foreground flex items-center justify-center mx-auto">
              <Stethoscope className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-foreground">No doctors found</h3>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              {searchQuery || selectedDept !== "ALL"
                ? "Try adjusting your search query or department filter."
                : "No practitioners registered in the hospital database yet."}
            </p>
            <Button
              size="sm"
              onClick={() => {
                setEditingDoctor(null);
                setIsAddModalOpen(true);
              }}
              className="text-xs gap-1.5 bg-blue-600 text-white cursor-pointer mt-2"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add First Doctor</span>
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-b border-border bg-muted/40">
                  <TableHead className="text-xs font-semibold">Doctor</TableHead>
                  <TableHead className="text-xs font-semibold">Department &amp; Speciality</TableHead>
                  <TableHead className="text-xs font-semibold">Weekly Days</TableHead>
                  <TableHead className="text-xs font-semibold">Shift Hours</TableHead>
                  <TableHead className="text-xs font-semibold">Daily Cap</TableHead>
                  <TableHead className="text-xs font-semibold">Status</TableHead>
                  <TableHead className="text-xs font-semibold text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredDoctors.map((doc) => (
                  <TableRow
                    key={doc.id}
                    className={`border-b border-border transition-colors hover:bg-muted/30 ${
                      !doc.is_active ? "opacity-60 bg-muted/10" : ""
                    }`}
                  >
                    {/* Doctor Avatar & Name */}
                    <TableCell className="text-xs">
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-9 h-9 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 ${
                            doc.is_active
                              ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                              : "bg-muted text-muted-foreground border border-border"
                          }`}
                        >
                          {getInitials(doc.name)}
                        </div>
                        <div>
                          <Link
                            href={`/doctors/${doc.id}`}
                            className="font-bold text-foreground hover:text-blue-600 hover:underline"
                          >
                            {doc.name}
                          </Link>
                          {doc.qualification && (
                            <p className="text-[11px] text-muted-foreground">
                              {doc.qualification}
                            </p>
                          )}
                        </div>
                      </div>
                    </TableCell>

                    {/* Department & Speciality */}
                    <TableCell className="text-xs">
                      <div className="font-semibold text-foreground">
                        {doc.speciality}
                      </div>
                      <span className="inline-block mt-0.5 text-[10px] px-1.5 py-0.2 rounded bg-muted text-muted-foreground border border-border">
                        {doc.department}
                      </span>
                    </TableCell>

                    {/* Working Days */}
                    <TableCell className="text-xs">
                      <div className="flex flex-wrap gap-1 max-w-[140px]">
                        {[1, 2, 3, 4, 5, 6, 7].map((d) => {
                          const isAvailable = doc.available_days?.includes(d);
                          return (
                            <span
                              key={d}
                              className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ${
                                isAvailable
                                  ? "bg-blue-600 text-white"
                                  : "bg-muted text-muted-foreground/40"
                              }`}
                            >
                              {DAY_LABELS[d]}
                            </span>
                          );
                        })}
                      </div>
                    </TableCell>

                    {/* Shift Hours & Slot duration */}
                    <TableCell className="text-xs">
                      <div className="flex items-center gap-1 font-medium text-foreground">
                        <Clock className="w-3 h-3 text-muted-foreground" />
                        <span>
                          {formatTime(doc.slot_start_time)} – {formatTime(doc.slot_end_time)}
                        </span>
                      </div>
                      <span className="text-[11px] text-muted-foreground">
                        {doc.slot_duration_minutes} min per consultation
                      </span>
                    </TableCell>

                    {/* Daily Capacity */}
                    <TableCell className="text-xs font-semibold text-foreground">
                      <span>{doc.max_daily_appointments}</span>
                      <span className="text-[11px] text-muted-foreground font-normal"> / day</span>
                    </TableCell>

                    {/* Status with Inline Toggle */}
                    <TableCell>
                      <button
                        type="button"
                        onClick={(e) => handleToggleStatus(doc, e)}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer border ${
                          doc.is_active
                            ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/20"
                            : "bg-muted text-muted-foreground border-border hover:bg-muted/80"
                        }`}
                        title="Click to toggle active status"
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            doc.is_active ? "bg-emerald-500" : "bg-muted-foreground"
                          }`}
                        />
                        <span>{doc.is_active ? "Active" : "Inactive"}</span>
                      </button>
                    </TableCell>

                    {/* Action Buttons */}
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Link
                          href={`/doctors/${doc.id}`}
                          className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-blue-600 transition-colors cursor-pointer"
                          title="Edit details"
                        >
                          <Edit className="w-3.5 h-3.5" />
                        </Link>

                        <Link
                          href={`/doctors/${doc.id}/schedule`}
                          className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-blue-600 transition-colors cursor-pointer"
                          title="Manage schedule overrides"
                        >
                          <Calendar className="w-3.5 h-3.5" />
                        </Link>

                        <button
                          type="button"
                          onClick={() => setDeletingDoctor(doc)}
                          className="p-1.5 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors cursor-pointer"
                          title="Deactivate doctor"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Card>

      {/* Add / Edit Doctor Form Dialog */}
      <DoctorFormDialog
        open={isAddModalOpen}
        onOpenChange={setIsAddModalOpen}
        doctor={editingDoctor}
        onSuccess={fetchDoctors}
      />

      {/* Delete / Deactivate Confirmation Dialog */}
      <Dialog
        open={!!deletingDoctor}
        onOpenChange={(open) => !open && setDeletingDoctor(null)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <div className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="w-5 h-5" />
              <DialogTitle className="text-base font-bold">
                Deactivate {deletingDoctor?.name}?
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-muted-foreground pt-1">
              Soft-deleting this doctor will mark their profile inactive. They will no longer be offered to callers by the AI receptionist. Existing appointments remain intact for hospital staff.
            </DialogDescription>
          </DialogHeader>

          <DialogFooter className="pt-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeletingDoctor(null)}
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
