"use client";
// Path: frontend/src/app/signup/page.tsx
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { TrendingUp, Eye, EyeOff, Loader2, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";

const schema = z.object({
  email:            z.string().email("Invalid email"),
  username:         z.string().min(3,"Min 3 chars").max(20,"Max 20 chars").regex(/^[a-zA-Z0-9_-]+$/,"Letters, numbers, _ and - only"),
  full_name:        z.string().min(2,"Min 2 chars").optional(),
  password:         z.string().min(8,"Min 8 chars").regex(/[A-Z]/,"Need uppercase").regex(/[0-9]/,"Need number"),
  confirm_password: z.string(),
}).refine((d) => d.password === d.confirm_password, { message: "Passwords don't match", path: ["confirm_password"] });
type FormData = z.infer<typeof schema>;

export default function SignupPage() {
  const router  = useRouter();
  const [showPw, setShowPw] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    setLoading(true); setError("");
    try {
      await api.post("/auth/signup", data);
      setSuccess(true);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || "Signup failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (success) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <CheckCircle2 className="h-16 w-16 text-green-400 mx-auto mb-4" />
        <h2 className="text-2xl font-bold text-white mb-2">Account Created!</h2>
        <p className="text-gray-400 mb-6">Your account is ready. Login to start trading.</p>
        <Link href="/login" className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold transition-all">Go to Login</Link>
      </div>
    </div>
  );

  const Field = ({ name, label, type = "text", placeholder }: { name: keyof FormData; label: string; type?: string; placeholder: string }) => (
    <div>
      <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">{label}</label>
      <input {...register(name)} type={type} placeholder={placeholder} autoComplete={name}
        className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all" />
      {errors[name] && <p className="text-red-400 text-xs mt-1">{String(errors[name]?.message)}</p>}
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 mb-6">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-white" />
            </div>
            <span className="text-2xl font-black bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">TradeAI</span>
          </Link>
          <h1 className="text-3xl font-bold text-white">Create your account</h1>
          <p className="text-gray-400 mt-2">Start trading smarter with AI today</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8">
          {error && <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 mb-5 text-red-400 text-sm">{error}</div>}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Field name="full_name" label="Full Name" placeholder="John Doe" />
            <Field name="username"  label="Username"  placeholder="john_trader" />
            <Field name="email"     label="Email"     type="email" placeholder="john@example.com" />
            <div>
              <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">Password</label>
              <div className="relative">
                <input {...register("password")} type={showPw ? "text" : "password"} placeholder="Min 8 chars, 1 uppercase, 1 number"
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 pr-10 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all" />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white">
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="text-red-400 text-xs mt-1">{errors.password.message}</p>}
            </div>
            <Field name="confirm_password" label="Confirm Password" type="password" placeholder="Re-enter your password" />
            <button type="submit" disabled={loading}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-all disabled:opacity-50 flex items-center justify-center gap-2 mt-2">
              {loading ? <><Loader2 className="h-4 w-4 animate-spin" />Creating...</> : "Create Account"}
            </button>
          </form>
          <p className="text-center text-gray-400 text-sm mt-6">
            Already have an account?{" "}
            <Link href="/login" className="text-blue-400 hover:underline font-medium">Login</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
