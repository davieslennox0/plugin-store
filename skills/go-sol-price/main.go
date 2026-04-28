// go-sol-price — query SOL/USDT spot price via OKX public ticker.
// No API key, no third-party deps — single self-contained Go binary.
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"
)

const (
	version = "1.0.0"
	apiURL  = "https://www.okx.com/api/v5/market/ticker?instId=SOL-USDT"
)

type tickerResp struct {
	Code string `json:"code"`
	Msg  string `json:"msg"`
	Data []struct {
		InstID string `json:"instId"`
		Last   string `json:"last"`
		Ts     string `json:"ts"`
	} `json:"data"`
}

func main() {
	if len(os.Args) > 1 {
		switch os.Args[1] {
		case "--version", "-V", "version":
			fmt.Printf("go-sol-price %s\n", version)
			return
		case "--help", "-h", "help":
			fmt.Println("Usage: go-sol-price [--version]")
			fmt.Println("Prints the current SOL/USDT spot price from OKX.")
			return
		}
	}

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(apiURL)
	if err != nil {
		fmt.Fprintf(os.Stderr, "fetch error: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	var r tickerResp
	if err := json.NewDecoder(resp.Body).Decode(&r); err != nil {
		fmt.Fprintf(os.Stderr, "decode error: %v\n", err)
		os.Exit(1)
	}
	if r.Code != "0" || len(r.Data) == 0 {
		fmt.Fprintf(os.Stderr, "api error: code=%s msg=%s\n", r.Code, r.Msg)
		os.Exit(1)
	}
	fmt.Printf("SOL/USDT: %s\n", r.Data[0].Last)
}
