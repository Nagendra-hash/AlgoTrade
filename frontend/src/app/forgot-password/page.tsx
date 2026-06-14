"use client";
// Path: frontend/src/app/forgot-password/page.tsx
import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { TrendingUp, Mail, ArrowLeft, Loader2, CheckCircle } from "lucide-react";
import { api } from "@/lib/api";

const schema = z.object({
  email: z.string().email("Invalid email address"),
});
type FormData = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [resetUrl, setResetUrl] = useState("");

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    setLoading(true);
    setError("");
    setSuccess(false);
    try {
      const res = await api.post("/auth/forgot-password", data);
      setSuccess(true);
      if (res.data?.reset_url) {
        setResetUrl(res.data.reset_url);
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 mb-6">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-white" />
            </div>
            <span className="text-2xl font-black bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">TradeAI</span>
          </Link>
          <h1 className="text-3xl font-bold text-white">Reset your password</h1>
          <p className="text-gray-400 mt-2">Enter your email and we&apos;ll send you a reset link</p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 mb-5 text-red-400 text-sm">{error}</div>
          )}

          {success ? (
            <div className="text-center space-y-4">
              <div className="mx-auto w-14 h-14 rounded-full bg-green-500/10 border border-green-500/20 flex items-center justify-center">
                <CheckCircle className="h-7 w-7 text-green-400" />
              </div>
              <p className="text-green-400 font-medium">Reset link sent!</p>
              <p className="text-gray-400 text-sm">
                If that email is registered, you&apos;ll receive a password reset link shortly.
              </p>
              {resetUrl && (
                <div className="bg-gray-800 rounded-xl p-4 mt-2">
                  <p className="text-gray-500 text-xs mb-2 font-semibold">Dev Mode — Reset Link</p>
                  <a
                    href={resetUrl}
                    className="text-blue-400 text-sm break-all hover:underline"
                  >
                    {resetUrl}
                  </a>
                </div>
              )}
              <Link
                href="/login"
                className="inline-flex items-center gap-2 text-blue-400 text-sm hover:underline mt-4"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to login
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
              <div>
                <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">Email</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-600" />
                  <input {...register("email")} type="email" placeholder="you@example.com" autoComplete="email"
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl pl-10 pr-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all" />
                </div>
                {errors.email && <p className="text-red-400 text-xs mt-1">{errors.email.message}</p>}
              </div>
              <button type="submit" disabled={loading}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-all disabled:opacity-50 flex items-center justify-center gap-2">
                {loading ? <><Loader2 className="h-4 w-4 animate-spin" />Sending...</> : "Send Reset Link"}
              </button>
            </form>
          )}
        </div>

        <p className="text-center text-gray-400 text-sm mt-6">
          <Link href="/login" className="inline-flex items-center gap-1 text-blue-400 hover:underline font-medium">
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to login
          </Link>
        </p>
      </div>
    </div>
  );
}
