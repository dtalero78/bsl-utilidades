//
//  ContentView.swift
//  BSLChat
//
//  Created by BSL on 2025-11-18.
//

import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack {
            Image(systemName: "message.fill")
                .imageScale(.large)
                .foregroundColor(.blue)
                .font(.system(size: 60))
            Text("BSL Chat")
                .font(.largeTitle)
                .fontWeight(.bold)
                .padding()
            Text("iOS App - En Desarrollo")
                .font(.subheadline)
                .foregroundColor(.gray)
        }
        .padding()
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
