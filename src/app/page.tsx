import { Footer } from "@/components/Footer";
import { ForCandidates } from "@/components/ForCandidates";
import { ForEmployers } from "@/components/ForEmployers";
import { GetStarted } from "@/components/GetStarted";
import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { WhyUs } from "@/components/WhyUs";

export default function Home() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <HowItWorks />
        <WhyUs />
        <ForEmployers />
        <ForCandidates />
        <GetStarted />
      </main>
      <Footer />
    </>
  );
}
