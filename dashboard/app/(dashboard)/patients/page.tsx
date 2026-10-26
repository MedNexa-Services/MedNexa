"use client";

import * as React from "react";
import Link from "next/link";
import { searchPatients, type PatientOut } from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { PatientFormDialog } from "@/components/patients/PatientFormDialog";
import { toast } from "sonner";
import {
  Users,
  Search,
  UserPlus,
  Phone,
  Mail,
  MapPin,
  Calendar,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  RefreshCw,
  User,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function PatientsPage() {
  const { hospitalId } = useHospital();

  const [searchQuery, setSearchQuery] = React.useState("");
  const [patients, setPatients] = React.useState<PatientOut[]>([]);
  const [totalCount, setTotalCount] = React.useState(0);
  const [isLoading, setIsLoading] = React.useState(true);
  const [pageIndex, setPageIndex] = React.useState(0);
  const pageSize = 15;

  const [formDialogOpen, setFormDialogOpen] = React.useState(false);

  // Normalize phone input: remove spaces, hyphens, ensure +91 if 10 digits
  const normalizePhone = (input: string) => {
    const clean = input.replace(/[\s-]/g, "");
    if (/^\d{10}$/.test(clean)) {
      return `+91${clean}`;
    }
    return clean;
  };

  const fetchPatients = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const queryTrimmed = searchQuery.trim();
      const params: Parameters<typeof searchPatients>[0] = {
        limit: pageSize,
        offset: pageIndex * pageSize,
      };

      if (hospitalId) {
        params.hospital_id = hospitalId;
      }

      if (queryTrimmed) {
        // If query starts with '+' or contains only digits and common phone characters
        const isPhoneLike = /^[+0-9\s-]+$/.test(queryTrimmed);
        if (isPhoneLike) {
          params.phone = normalizePhone(queryTrimmed);
        } else {
          params.name = queryTrimmed;
        }
      }

      const res = await searchPatients(params);
      setPatients(res.items);
      setTotalCount(res.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load patient records";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, [hospitalId, searchQuery, pageIndex]);

  React.useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPageIndex(0);
    fetchPatients();
  };

  const handleClearSearch = () => {
    setSearchQuery("");
    setPageIndex(0);
  };

  const handleQuickPhonePreset = (phoneStr: string) => {
    setSearchQuery(phoneStr);
    setPageIndex(0);
  };

  const getInitials = (nameStr: string) => {
    const parts = nameStr.trim().split(" ");
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
    return nameStr.slice(0, 2).toUpperCase();
  };

  const formatDate = (isoStr: string) => {
    try {
      return new Date(isoStr).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Users className="w-6 h-6 text-primary" />
            Patient Directory
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Search registered patients by phone number or name, view medical profiles, and track appointment histories.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchPatients()}
            className="gap-1.5 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </Button>

          <Button
            size="sm"
            onClick={() => setFormDialogOpen(true)}
            className="gap-1.5 cursor-pointer shadow-sm bg-primary text-primary-foreground"
          >
            <UserPlus className="w-4 h-4" />
            <span>Register Patient</span>
          </Button>
        </div>
      </div>

      {/* Search Toolbar */}
      <Card className="p-4 space-y-3 bg-card border-border">
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row items-center gap-2">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by phone number (e.g. +919876543210 or 9876543210) or patient name..."
              className="pl-9 h-10 text-xs"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={handleClearSearch}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
              >
                Clear
              </button>
            )}
          </div>

          <Button type="submit" size="sm" className="h-10 px-4 cursor-pointer gap-1.5 shrink-0">
            <Search className="w-3.5 h-3.5" />
            <span>Search</span>
          </Button>
        </form>

        {/* Quick Seed Presets */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border/60 text-xs">
          <span className="text-muted-foreground font-semibold flex items-center gap-1">
            <Phone className="w-3 h-3" />
            Quick Presets:
          </span>
          <button
            type="button"
            onClick={() => handleQuickPhonePreset("")}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
              searchQuery === ""
                ? "bg-primary text-primary-foreground font-semibold"
                : "bg-muted hover:bg-muted/80 text-foreground"
            }`}
          >
            All Patients
          </button>
          <button
            type="button"
            onClick={() => handleQuickPhonePreset("+919876543210")}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
              searchQuery === "+919876543210"
                ? "bg-primary text-primary-foreground font-semibold"
                : "bg-muted hover:bg-muted/80 text-foreground"
            }`}
          >
            +91 98765 43210 (Rahul &amp; Sita)
          </button>
          <button
            type="button"
            onClick={() => handleQuickPhonePreset("+919900112233")}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
              searchQuery === "+919900112233"
                ? "bg-primary text-primary-foreground font-semibold"
                : "bg-muted hover:bg-muted/80 text-foreground"
            }`}
          >
            +91 99001 12233 (Mohan Lal)
          </button>
          <button
            type="button"
            onClick={() => handleQuickPhonePreset("+919812345678")}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
              searchQuery === "+919812345678"
                ? "bg-primary text-primary-foreground font-semibold"
                : "bg-muted hover:bg-muted/80 text-foreground"
            }`}
          >
            +91 98123 45678 (Priya Sharma)
          </button>
        </div>
      </Card>

      {/* Patients Table */}
      <Card className="border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12"></TableHead>
              <TableHead>Patient Name</TableHead>
              <TableHead>Phone Number</TableHead>
              <TableHead>Age &amp; Gender</TableHead>
              <TableHead>Email / Address</TableHead>
              <TableHead>Registered On</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [1, 2, 3, 4, 5].map((i) => (
                <TableRow key={i}>
                  <TableCell><div className="w-8 h-8 rounded-full bg-muted animate-pulse" /></TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <div className="w-28 h-3.5 bg-muted animate-pulse rounded" />
                      <div className="w-16 h-2.5 bg-muted/60 animate-pulse rounded" />
                    </div>
                  </TableCell>
                  <TableCell><div className="w-24 h-3.5 bg-muted animate-pulse rounded" /></TableCell>
                  <TableCell><div className="w-16 h-5 rounded bg-muted animate-pulse" /></TableCell>
                  <TableCell><div className="w-32 h-3.5 bg-muted animate-pulse rounded" /></TableCell>
                  <TableCell><div className="w-20 h-3.5 bg-muted animate-pulse rounded" /></TableCell>
                  <TableCell className="text-right"><div className="w-24 h-7 rounded bg-muted animate-pulse ml-auto" /></TableCell>
                </TableRow>
              ))
            ) : patients.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-36 text-center text-muted-foreground">
                  <div className="flex flex-col items-center justify-center gap-2 max-w-sm mx-auto">
                    <AlertCircle className="w-8 h-8 text-muted-foreground/50" />
                    <span className="text-sm font-semibold text-foreground">No patients found</span>
                    <p className="text-xs text-muted-foreground">
                      No patients match your search query &ldquo;{searchQuery}&rdquo;.
                    </p>
                    <div className="flex gap-2 mt-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleClearSearch}
                        className="text-xs cursor-pointer"
                      >
                        Clear Search
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => setFormDialogOpen(true)}
                        className="text-xs cursor-pointer"
                      >
                        Register Patient
                      </Button>
                    </div>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              patients.map((pat) => (
                <TableRow key={pat.id} className="hover:bg-muted/40 transition-colors">
                  {/* Avatar Initials */}
                  <TableCell>
                    <div className="w-9 h-9 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center border border-primary/20">
                      {getInitials(pat.name)}
                    </div>
                  </TableCell>

                  {/* Name */}
                  <TableCell>
                    <div className="space-y-0.5">
                      <Link
                        href={`/patients/${pat.id}`}
                        className="font-bold text-xs text-foreground hover:text-primary transition-colors block"
                      >
                        {pat.name}
                      </Link>
                      <span className="text-[11px] font-mono text-muted-foreground block truncate max-w-[140px]">
                        ID: {pat.id.slice(0, 8)}...
                      </span>
                    </div>
                  </TableCell>

                  {/* Phone */}
                  <TableCell>
                    <span className="font-semibold text-xs text-foreground flex items-center gap-1.5">
                      <Phone className="w-3 h-3 text-muted-foreground" />
                      {pat.phone}
                    </span>
                  </TableCell>

                  {/* Age & Gender */}
                  <TableCell>
                    <div className="text-xs space-x-1">
                      <span className="font-medium text-foreground">
                        {pat.age ? `${pat.age} yrs` : "—"}
                      </span>
                      {pat.gender && (
                        <Badge variant="outline" className="text-[10px] capitalize">
                          {pat.gender.toLowerCase()}
                        </Badge>
                      )}
                    </div>
                  </TableCell>

                  {/* Email & Address */}
                  <TableCell>
                    <div className="text-xs space-y-0.5 text-muted-foreground max-w-[200px] truncate">
                      {pat.email ? (
                        <span className="flex items-center gap-1 text-[11px] block truncate">
                          <Mail className="w-3 h-3 shrink-0" />
                          {pat.email}
                        </span>
                      ) : pat.address ? (
                        <span className="flex items-center gap-1 text-[11px] block truncate">
                          <MapPin className="w-3 h-3 shrink-0" />
                          {pat.address}
                        </span>
                      ) : (
                        <span className="text-[11px] italic">No contact details</span>
                      )}
                    </div>
                  </TableCell>

                  {/* Registered On */}
                  <TableCell>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Calendar className="w-3 h-3" />
                      <span>{formatDate(pat.created_at)}</span>
                    </div>
                  </TableCell>

                  {/* Actions */}
                  <TableCell className="text-right">
                    <Link
                      href={`/patients/${pat.id}`}
                      className="inline-flex items-center justify-center h-8 px-3 rounded-md text-xs font-medium border border-input bg-background hover:bg-muted text-foreground transition-colors cursor-pointer gap-1"
                    >
                      <span>View History</span>
                      <ExternalLink className="w-3 h-3 text-muted-foreground" />
                    </Link>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>

        {/* Pagination Bar */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-muted-foreground bg-muted/20">
          <div>
            Showing{" "}
            <span className="font-semibold text-foreground">
              {totalCount === 0 ? 0 : pageIndex * pageSize + 1}
            </span>{" "}
            to{" "}
            <span className="font-semibold text-foreground">
              {Math.min((pageIndex + 1) * pageSize, totalCount)}
            </span>{" "}
            of <span className="font-semibold text-foreground">{totalCount}</span> patients
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={pageIndex === 0}
              onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
              className="h-8 gap-1 cursor-pointer"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>Previous</span>
            </Button>
            <span className="text-xs font-medium px-2">Page {pageIndex + 1}</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={(pageIndex + 1) * pageSize >= totalCount}
              onClick={() => setPageIndex((p) => p + 1)}
              className="h-8 gap-1 cursor-pointer"
            >
              <span>Next</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </Card>

      {/* Patient Register Dialog */}
      <PatientFormDialog
        open={formDialogOpen}
        onOpenChange={setFormDialogOpen}
        onSuccess={fetchPatients}
      />
    </div>
  );
}
